# IDDE Sensor Health Report

## Overview

The IDDE Health Report System offers comprehensive insights into sensor maintenance by generating summary and detailed reports. These reports provide status updates, data integrity checks, and visual representations of key metrics, helping to ensure the reliability and efficiency of sensor systems.

## Project Structure

- **main.py**: The main script that coordinates data collection and report generation. It handles errors and sends notifications via email.
- **get_raw_data.py**: Responsible for collecting raw data, including scraping CSV files and image metadata.
- **get_reports.py**: Processes the collected data to generate summary and detailed reports.
- **utils.py**: Contains utility functions, including email sending and status determination.
- **config_example.json**: Configuration file containing settings for data sources, thresholds, and email notifications.

## Summary Report
- **Battery Status Monitoring**
  - The script checks the latest battery reading from the sensor and classifies the status as `CRITICAL`, `LOW`, or `OK` based on predefined thresholds:
    - `CRITICAL_BATTERY_LIMIT`: 2500
    - `LOW_BATTERY_LIMIT`: 3500
  - If the lastest battery reading is invalid or missing (indicated by a value of `-88`), the script uses the last valid reading to determine the status.

- **Data Update Monitoring**
  - This script checks the timestamp of the last modification (PDT) (currently scraping from the BOSL website) to determine if the data has been updated within the last 24 hours.
  - The timestamp of the last modification of a CSV file is retrieved and compared against the current time (PDT) to calculate the time difference in hours.
  - The update status is classified as:
    - `YES` if the data has been updated within the last 24 hours.
    - `NO` if the data has not been updated within the last 24 hours.

- **Data Completeness Assessment**
  - Except for CAM sensors, this script evaluates the completeness of the data collected from all other sensors by comparing the actual number of data points with the expected number.
  - The expected number of data points is calculated based on the date range of the data (from 1st data point to last data point) and a predefined expected frequency (6min).
  - Code: `expected_timepoints = len(pd.date_range(start=sensor_data['datetime'].min(), end=sensor_data['datetime'].max(), freq=EXPECTED_FREQUENCY))`
  - The percentage of missing data points is then calculated as: (actual number of data points / the expected number of data point) * 100 = percent_exist. Then it subtracts the percentage of data existed from 100%, giving the percentage of data that is missing.

- **High-Quality Images Assessment**
  - This script filters and assesses the quality of images based on their file size.
  - An upper bound for the image size is set to 100kb, and images exceeding this size are excluded from further analysis.
  - The script then determines the maximum file size within the filtered dataset.
  - The percentage of high-quality images is calculated by identifying images that are at least a certain proportion (`IMAGE_QUALITY_THRESHOLD` = 0.75) of this maximum size.
  - The formula used is:
    - `percent_hq_images = int(round((len(subdf[subdf['size'] >= IMAGE_QUALITY_THRESHOLD * max_size]) / len(subdf)) * 100))`
  - This percentage indicates how many of the images meet the high-quality threshold based on file size.


## Contact

If you have any questions, suggestions, or feedback, please feel free to contact us:

- **Duy Nguyen**: [duyn@sccwrp.org](mailto:duyn@sccwrp.org)
- **Elizabeth Fassman-Beck**: [elizabethfb@sccwrp.org](mailto:elizabethfb@sccwrp.org)
