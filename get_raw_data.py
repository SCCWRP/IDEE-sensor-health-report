import pandas as pd
import json, os
import time
from datetime import timedelta
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils import *


# NOTE: this might take 1 hour to run

def get_raw_data():
   
    start_time = time.time()
    # Configuration
    CONFIG = json.loads(open('config.json', 'r').read())
    data_url = CONFIG.get('DATA_URL')
    image_url = CONFIG.get('IMAGES_URL')
    valid_patterns = CONFIG.get('VALID_PATTERNS')
    low_batt_threshold = CONFIG.get('LOW_BATTERY_LIMIT')
    missing_timestamp_threshold = CONFIG.get('MISSING_TIMESTAMP_CHECK')
    mail_from = CONFIG.get('MAIL_FROM')
    mail_to = CONFIG.get('MAIL_TO')
    mail_server = CONFIG.get('MAIL_SERVER')

    # Initilize driver
    options = Options()
    options.add_argument('--headless')  # Run Chrome in headless mode
    options.add_argument('--no-sandbox')  # Bypass OS security model
    options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
    options.add_argument('--disable-gpu')  # Disable GPU hardware acceleration
    options.add_argument('--remote-debugging-port=9222')  # Enable remote debugging
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)


    ############################################################ SCRAPE CSV FILES FROM WEBPAGE ####################################################
    print("Scraping metadata for the CSV files")
    # Open the webpage
    driver.get(data_url)

    # Find all the table rows
    rows = driver.find_elements(By.XPATH, '//tr')

    # Initialize an empty list to store the data
    data_list = []

    # Iterate over each row and extract the required details
    for index, row in enumerate(rows):
        a_tags = row.find_elements(By.TAG_NAME, 'a')
        for a_tag in a_tags:
            href = a_tag.get_attribute('href')
            if ".csv" not in href:
                continue
            else:
                td_elements = row.find_elements(By.TAG_NAME, 'td')
                td_texts = [td.text for td in td_elements if td.text.strip() != '']
                if len(td_texts) >= 3:
                    pattern = "_".join(td_texts[0].replace(".csv", "").lower().split('_')[:2])
                    if pattern in valid_patterns:
                        filename = td_texts[0]
                        print("getting files:")
                        print(filename)
                        last_modified = td_texts[1]
                        size = td_texts[2]
                        data_list.append({
                            'filename': filename,
                            'data_location': href,
                            'last_modified': (pd.Timestamp(last_modified) - timedelta(hours=17)), # Convert from AUS time to PST time
                            'size': size
                        })

    # Build dataframe
    df = pd.DataFrame(data_list, columns=['filename', 'data_location', 'last_modified', 'size'])
    df = df.sort_values(by=['filename'])

    #Remove the test files. Those files end with 1,2. Confirmed by Jerod Gray 06/12/24
    df = df[~df['filename'].str.endswith(('1.csv', '2.csv'))]
    #df['size'] = pd.to_numeric( df['size'].str.replace("K","").replace("M", "") )
    df['size'] = "" # No need to look at the size
    df.to_csv('data/metadata-logger.csv', index=False)
    print("Done!")
    ###############################################################################################################################################




    ########################################################### SCRAPE DATA FROM IMAGES ###########################################################
    print("Scraping metadata for the images")
    driver.get(image_url)

    # Find all the table rows
    rows = driver.find_elements(By.XPATH, '//tr')

    wait = WebDriverWait(driver, 60)

    # get all image URLs of interest
    img_urls = [
        os.path.join(a_tag.get_attribute('href'), "images").rsplit('/', 1)[0]
        for row in rows
        for a_tag in row.find_elements(By.TAG_NAME, 'a')
        if "_".join(a_tag.get_attribute("href").split("/")[-2].split("_")[:2]).lower() in valid_patterns
    ]

    # Iterate over each row and extract the required details
    df_final = pd.DataFrame()
    for url in img_urls:
        print(f"Clicking {url}")
        driver.get(url)
        
        # Wait until the table rows are present in the new page
        wait.until(EC.presence_of_all_elements_located((By.XPATH, '//tr')))
        last_modified = pd.Timestamp(driver.find_elements(By.XPATH, "//table/tbody/tr[4]")[0].find_elements(By.TAG_NAME, "td")[2].text)
        last_modified = last_modified + pd.Timedelta(hours=8)

        driver.get(os.path.join(url, "images"))
        # Get all rows, then extract <a> and all <td>s with needed info
        img_filename_list = []
        size_list = []
        rows = [x for x in driver.find_elements(By.XPATH, '//tr')][3:-1]
        for row in rows:
            img_filename = row.find_elements(By.TAG_NAME, 'a')[0].text
            print(img_filename)
            td_elements = row.find_elements(By.TAG_NAME, 'td')
            td_texts = [td.text for td in td_elements if td.text.strip() != '']
            size = td_texts[2]
            img_filename_list.append(img_filename)
            size_list.append(size)
        df = pd.DataFrame({
            'img_filename': img_filename_list,
            'size': size_list
        })
        df['data_location'] = url
        df['last_modified'] = last_modified
        df_final = pd.concat([df_final, df])

    # Initialize a dictionary to store the parsed data
    all_data = {}

    for url in img_urls:
        print(f"Clicking {url}")
        driver.get(os.path.join(url, "status"))
        
        # Wait until the data is present on the page
        pre_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'pre')))
        
        # Extract the text content
        data = pre_element.text
        
        # Split the data into lines
        lines = data.split('\n')
        
        # Initialize a list to store data for the current URL
        url_data = []
        
        # Process each line
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
            # Split the line by commas
            split_line = line.split(',')
            # Add the split line to the list for the current URL
            url_data.append(split_line)
        
        # Add the list to the dictionary with the URL as the key
        all_data[url] = url_data[-1]

    data_list = []

    for k, v in all_data.items():
        data_list.append(
            {
                'data_location': k.replace("status", "images"),
                'latest_battery_level': v[3]
            }
        )

    tmp = pd.DataFrame(data_list)

    df_final = df_final.merge(
        tmp,
        how='left',
        on=['data_location']
    )

    df_final.to_csv("data/metadata-images.csv", index=False)
    end_time = time.time()
    runtime = end_time - start_time

    print(f"Runtime: {runtime} seconds")
    print("Done")
    ###############################################################################################################################################
