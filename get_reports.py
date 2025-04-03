import pandas as pd
import json, pytz
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from fpdf import FPDF
from utils import determine_status
from datetime import timedelta
from datetime import datetime, timezone
import sqlite3
from utils import *



ODD_FILENAMES = {
    'IDDE_CULVERT_DT.csv': 'CULVERT_RP_DT.csv',
    'GOLF_CULVERT_RADAR.csv': 'CULVERT_BC_RAD.csv',
    'IDDE_DIVERSION_DT.csv': 'DIVERSION_BC_DTTURB.csv',
    'DIVERSION_RADAR.csv': 'DIVERSION_BC_RAD.csv', 
    'DIVERSION_CAM': 'DIVERSION_BC_CAM'
}

def get_reports():
    ############################################################ GENERATE SUMMARY REPORT ########################################################
    print("GENERATING SUMMARY REPORT")
    # Configuration
    CONFIG = json.loads(open('config.json', 'r').read())
    CRITICAL_BATTERY_LIMIT = CONFIG.get('CRITICAL_BATTERY_LIMIT')
    LOW_BATTERY_LIMIT = CONFIG.get('LOW_BATTERY_LIMIT')
    IMAGE_QUALITY_THRESHOLD = CONFIG.get('IMAGE_QUALITY_THRESHOLD')
    EXPECTED_FREQUENCY = CONFIG.get('EXPECTED_FREQUENCY_MIN')

    # Get today dates
    today = datetime.now(timezone.utc)
    _24_hours_ago = pd.Timestamp(today - timedelta(hours=24))
    todayyear = today.year
    todaymonth = today.month
    todaydate = today.day

    # Load the data
    metadata_logger = pd.read_csv("data/metadata-logger.csv")
    metadata_images = pd.read_csv("data/metadata-images.csv")

    # Process CSV data
    metadata_logger['filename'] = metadata_logger['filename'].replace(ODD_FILENAMES)
    metadata_logger[['sensor_location', 'sensor_cover', 'sensor_type']] = metadata_logger['filename'].str.extract(r'(\w+)_(\w+)_(\w+)\.csv')
    metadata_logger[['sensor_location', 'sensor_cover', 'sensor_type']] = metadata_logger[['sensor_location', 'sensor_cover', 'sensor_type']].map(str.upper)

    tmp = []


    for (location, cover, type_), subdf in metadata_logger.groupby(['sensor_location', 'sensor_cover', 'sensor_type']):
        print((location, cover, type_))
        try:
            sensor_data = pd.read_csv(subdf['data_location'].iloc[0])
        except Exception as e:
            continue

        sensor_data = sensor_data.rename(columns={'SiteName': 'datetime', 'CBC': 'Batt'})
        sensor_data['datetime'] = pd.to_datetime(sensor_data['datetime'], format='%d/%m/%y %I:%M:%S %p')
        sensor_data = sensor_data.sort_values('datetime')

        # Battery Check
        sensor_data['Batt'] = pd.to_numeric(sensor_data['Batt'], errors='coerce').fillna(-88)
        latest_batt_level = sensor_data['Batt'].iloc[-1]

        if (latest_batt_level != -88) and (latest_batt_level < CRITICAL_BATTERY_LIMIT):
            battery_status = 'CRITICAL'
        elif (latest_batt_level != -88) and (CRITICAL_BATTERY_LIMIT <= latest_batt_level <= LOW_BATTERY_LIMIT):
            battery_status = 'LOW'
        elif (latest_batt_level != -88) and (latest_batt_level > LOW_BATTERY_LIMIT):
            battery_status = 'OK'
        else:
            battery_status = f"Latest value cannot be read - Latest readable value: {sensor_data[sensor_data['Batt'] != -88]['Batt'].iloc[-1]}"

        # Last Updated Check
        last_modified = pd.Timestamp(sensor_data['datetime'].iloc[-1])
        last_updated_status = 'NO' if (datetime.today() - last_modified).total_seconds()/3600 > 24 else 'YES'
        last_updated_entry = last_modified

        lowest_battery_value = sensor_data['Batt'].iloc[-1]
        expected_timepoints = (24 * 60) // int(CONFIG.get('MISSING_TIMESTAMP_CHECK'))
        if last_updated_status == 'YES':
            percent_missing = int(
                round(
                    max(
                        0, 
                        100 - ((len(sensor_data[sensor_data['datetime'] >= (_24_hours_ago.to_datetime64())]) / expected_timepoints) * 100)
                    )
                )
            )
        else:
            percent_missing = "Cannot be determined - Data was not available for the last within 24 hours."

        # Value Range Checks for RAD and TURB
        value_status = ''
        num_bad_values = 0

        if type_ == 'RAD':
            # Check for 'ANGLE' column values outside [75, 85]
            if 'ANGLE' in sensor_data.columns:
                bad_values = sensor_data[(sensor_data['ANGLE'] < 75) | (sensor_data['ANGLE'] > 85)]
                num_bad_values = len(bad_values)
                if num_bad_values > 0:
                    value_status = f"Angle value (degrees) out of range (Normal range: [75,85]) - {num_bad_values} bad values"

        elif type_ == 'TURB':
            # Check for 'Turbwo' column values greater than 10
            if 'Turbwo' in sensor_data.columns:
                bad_values = sensor_data[sensor_data['Turbwo'] > 10]
                num_bad_values += len(bad_values)
                if num_bad_values > 0:
                    value_status += f"Turbidity without LED values out of range (Normal range: [0,10]) - {num_bad_values} bad values; "

            # Check for 'EC' column values equal to 0
            if 'EC' in sensor_data.columns:
                bad_values = sensor_data[sensor_data['EC'] == 0]
                num_bad_values += len(bad_values)
                if len(bad_values) > 0:
                    value_status += f"EC value is 0 - {len(bad_values)} bad values"

        report = subdf.assign(
            battery_status=battery_status,
            lowest_battery_value=lowest_battery_value,
            last_updated_status=last_updated_status,
            last_updated_entry=last_updated_entry,
            percent_missing=percent_missing,
            value_status=value_status.strip('; ')
        )

        tmp.append(report[['sensor_location', 'sensor_cover', 'sensor_type', 'last_modified', 'size', 'battery_status', 'lowest_battery_value', 'last_updated_status', 'last_updated_entry', 'percent_missing', 'data_location', 'value_status']])

    data_report = pd.concat(tmp)

    # Extracted 'sensor_location', 'sensor_cover', 'sensor_type'
    metadata_images['extracted_part'] = metadata_images['data_location'].str.extract(r'\/(\w+_\w+_\w+)')[0]
    metadata_images['extracted_part'] = metadata_images['extracted_part'].replace(ODD_FILENAMES)
    metadata_images[['sensor_location', 'sensor_cover', 'sensor_type']] = metadata_images['extracted_part'].str.split('_', expand=True)
    metadata_images['sensor_location'] = metadata_images['sensor_location'].str.upper()

    tmp = []
    for (location, cover, type_), subdf in metadata_images.groupby(['sensor_location', 'sensor_cover', 'sensor_type']):
        last_modified = (pd.Timestamp(subdf['last_modified'].iloc[0])).replace(tzinfo=timezone.utc)
        last_updated_status = 'NO' if (today - last_modified).total_seconds()/3600 > 24 else 'YES'
        last_updated_entry = last_modified
        subdf['size'] = pd.to_numeric(subdf['size'].str.replace('K', ''))

        # Define an upper bound for size (100kb)
        subdf = subdf[subdf['size'] <= 100]
        max_size = subdf['size'].max()
        percent_hq_images = int(round((len(subdf[subdf['size'] >= IMAGE_QUALITY_THRESHOLD * max_size]) / len(subdf)) * 100))

        if (subdf['latest_battery_level'].iloc[0] != -88) and (subdf['latest_battery_level'].iloc[0] <= CRITICAL_BATTERY_LIMIT):
            battery_status = 'CRITICAL'
        elif CRITICAL_BATTERY_LIMIT < subdf['latest_battery_level'].iloc[0] <= LOW_BATTERY_LIMIT:
            battery_status = 'LOW'
        elif subdf['latest_battery_level'].iloc[0] == -88:
            battery_status = f"{subdf[subdf['latest_battery_level'] != -88]['latest_battery_level'].iloc[0]}"
        else:
            battery_status = 'OK'

        report = pd.DataFrame({
            'sensor_location': [location],
            'sensor_cover': [cover],
            'sensor_type': [type_],
            'last_modified': [last_modified],
            'last_updated_status': [last_updated_status],
            'last_updated_entry': [last_updated_entry],
            'percent_hq_images': [percent_hq_images],
            'max_image_size': [max_size],
            'data_location': [subdf['data_location'].iloc[0]],
            'lowest_battery_value': [subdf['latest_battery_level'].iloc[0]],
            'battery_status': [battery_status]
        })
        tmp.append(report)

    image_report = pd.concat(tmp)

    # Combine and sort final report
    combined_df = pd.concat([data_report, image_report]).sort_values(['sensor_location', 'sensor_cover', 'sensor_type']).reset_index(drop=True)

    # Group the data
    grouped = combined_df.groupby(['sensor_location', 'sensor_cover'])

    # Initialize an empty list to hold the processed groups
    processed_groups = []

    # Iterate over each group
    for (location, cover), group in grouped:
        if location == 'DIVERSION':  # for this location, DT and TURB are together
            required_sensor_types = ['DTTURB', 'RAD', 'CAM']
        else:
            required_sensor_types = ['DT', 'TURB', 'RAD', 'CAM']
        present_sensors = group['sensor_type'].tolist()
        missing_sensors = [sensor for sensor in required_sensor_types if sensor not in present_sensors]
        
        for sensor in missing_sensors:
            group = pd.concat([group, pd.DataFrame({
                'sensor_location': [location],
                'sensor_cover': [cover],
                'sensor_type': [f'{sensor}-UNAVAILABLE'],
                'value': [None]  # or some placeholder value
            })], ignore_index=True)
        
        group = group.sort_values(by='sensor_type', key=lambda col: [required_sensor_types.index(sensor.split('-')[0]) for sensor in col])
        processed_groups.append(group)

    # Combine all processed groups into a single DataFrame
    final_report = pd.concat(processed_groups).reset_index(drop=True)

    # Create PDF
    pdf = PDF()
    pdf.add_page()

    # Add note at the beginning
    pdf.add_note(
    f"Runtime (UTC): {today}\nBattery Status Definition:\n'OK' >{LOW_BATTERY_LIMIT}\n'LOW' - [{CRITICAL_BATTERY_LIMIT}, {LOW_BATTERY_LIMIT}]\n'CRITICAL' < {CRITICAL_BATTERY_LIMIT}")

    # Process each location and add text
    locations = final_report[['sensor_location', 'sensor_cover']].drop_duplicates()
    for _, loc in locations.iterrows():
        location_cover = f"{loc['sensor_location']} {loc['sensor_cover']}"
        
        # Add chapter title for location
        pdf.chapter_title(location_cover)
        
        # Collect status texts
        status_texts = []
        location_data = final_report[(final_report['sensor_location'] == loc['sensor_location']) & (final_report['sensor_cover'] == loc['sensor_cover'])]
        for _, row in location_data.iterrows():
            status_texts.append(determine_status(row))
        
        # Combine all status texts into one body and add to chapter body
        chapter_body_text = "\n".join(status_texts)
        pdf.chapter_body(chapter_body_text)

    # Save PDF
    pdf_output_path = f'reports/Summary_Report_{todayyear}-{todaymonth}-{todaydate}.pdf'
    pdf.output(pdf_output_path)


    #############################################################################################################################################




    ############################################################ GENERATE DETAILED REPORT ########################################################
    print("GENERATING DETAILED REPORT")
    report = []
    pdf = FPDF()

    # Format the output path with today's date
    pdf_output_path = f'reports/Detailed_Report_{todayyear}-{todaymonth}-{todaydate}.pdf'

    sensor_data_list = []
    metrics_data_list = []  # New list to store metrics

    for (location, cover, type_), subdf in final_report.groupby(['sensor_location', 'sensor_cover', 'sensor_type'], sort=False):
        print((location, cover, type_))
        if ('UNAVAILABLE' in type_) or (type_ == 'CAM'):
            report_text = ""
        else:
            try:
                sensor_data = pd.read_csv(subdf['data_location'].iloc[0])
            except Exception as e:
                continue
            
            sensor_data = sensor_data.rename(
                columns={'SiteName': 'datetime', 'CBC': 'Batt', 'DEPTH': 'depth', 'Depth': 'depth', 'TURBwo': 'turbwo'}
            )
            # Convert from UTC to PST
            sensor_data['datetime'] = pd.to_datetime(sensor_data['datetime'], format='%d/%m/%y %I:%M:%S %p')
            sensor_data = sensor_data.sort_values('datetime')
            last_timestamp_recorded = sensor_data['datetime'].iloc[-1]
            current_battery_level = sensor_data['Batt'].iloc[-1]

            # Initialize metrics
            value_status = 'OK'
            problematic_timestamps = []
            missing_periods_list = []

            # Check for missing data periods
            if subdf['last_updated_status'].iloc[0] == 'YES':
                tmp = sensor_data[sensor_data['datetime'] >= (_24_hours_ago.to_datetime64())].reset_index(drop=True)
                
                # Find missing data periods
                tmp['time_diff'] = tmp['datetime'].diff()
                missing_data_periods = tmp[tmp['time_diff'] >= pd.Timedelta(minutes=CONFIG.get('MISSING_TIMESTAMP_CHECK'))]
                
                for idx, row in missing_data_periods.iterrows():
                    prev_row = tmp.iloc[idx - 1]
                    missing_periods_list.append((prev_row['datetime'].strftime('%Y-%m-%d %H:%M:%S'), row['datetime'].strftime('%Y-%m-%d %H:%M:%S')))
                
                missing_periods_text = str(missing_periods_list) if missing_periods_list else 'No missing data periods.'

                # Check data based on sensor type
                if type_ == 'RAD':
                    if 'ANGLE' in tmp.columns:
                        out_of_range = tmp[(tmp['ANGLE'] < 75) | (tmp['ANGLE'] > 85)]
                        if not out_of_range.empty:
                            value_status = f"ANGLE VALUE OUT OF RANGE [75,85] - {len(out_of_range)} bad values"
                            problematic_timestamps.extend(out_of_range['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist())

                elif type_ == 'TURB':
                    if 'turbwo' in tmp.columns:
                        out_of_range_turbwo = tmp[tmp['turbwo'] > 10]
                        if not out_of_range_turbwo.empty:
                            value_status += f"TURBWO VALUE OUT OF RANGE [>10] - {len(out_of_range_turbwo)} bad values; "
                            problematic_timestamps.extend(out_of_range_turbwo['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist())

                    if 'EC' in tmp.columns:
                        out_of_range_ec = tmp[tmp['EC'] == 0]
                        if not out_of_range_ec.empty:
                            value_status += f"EC VALUE IS 0 - {len(out_of_range_ec)} bad values"
                            problematic_timestamps.extend(out_of_range_ec['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist())
            else:
                value_status = 'Cannot be determined. Data is not up-to-date.'
                missing_periods_text = 'Cannot be determined. Data is not up-to-date.'

            # Prepare the report text
            report_text = f"Last Timestamp Recorded: {last_timestamp_recorded}\n" \
                        f"Current Battery Level: {current_battery_level}\n" \
                        f"Data are missing in these periods: {missing_periods_text}\n" \
                        f"Value Range Check: {value_status}\n" \
                        f"Problematic Timestamps for Value Range Check: {', '.join(problematic_timestamps) if problematic_timestamps else 'None'}\n"
            
            pdf.add_page()
            # Add section header with bold and larger font size
            pdf.set_font("Arial", 'B', size=16)
            pdf.cell(0, 10, f"{location} {cover} {type_}", ln=True)
            
            # Add report text with normal font size
            pdf.set_font("Arial", size=12)
            pdf.multi_cell(0, 10, report_text)
            
            sensor_data = sensor_data.assign(
                sensor_location=location,
                sensor_cover=cover,
                sensor_type=type_
            )
            sensor_data_list.append(sensor_data)

            # Collect metrics data
            metrics_data_list.append({
                'sensor_location': location,
                'sensor_cover': cover,
                'sensor_type': type_,
                'last_timestamp_recorded': last_timestamp_recorded.strftime('%Y-%m-%d %H:%M:%S'),
                'current_battery_level': current_battery_level,
                'missing_periods': str(missing_periods_list),
                'value_status': value_status,
                'problematic_timestamps': ', '.join(problematic_timestamps),
                'report_date': f"{todayyear}-{todaymonth}-{todaydate}"
            })

    metrics_df = pd.DataFrame(metrics_data_list)
    sensor_data_final = pd.concat(sensor_data_list)

    conn = sqlite3.connect('sensor_metrics.db')
    cursor = conn.cursor()
    for _, row in metrics_df.iterrows():
        # Convert missing periods and problematic timestamps to strings
        missing_periods = str(row['missing_periods']) if row['missing_periods'] else 'No missing data periods.'
        problematic_timestamps = ', '.join(row['problematic_timestamps']) if row['problematic_timestamps'] else 'None'
        cursor.execute('''
            INSERT INTO detailed_report_metrics (
                sensor_location, 
                sensor_cover, 
                sensor_type, 
                last_timestamp_recorded, 
                current_battery_level, 
                missing_periods, 
                value_status, 
                problematic_timestamps,
                report_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            row['sensor_location'],
            row['sensor_cover'],
            row['sensor_type'],
            row['last_timestamp_recorded'],
            row['current_battery_level'],
            missing_periods,
            row['value_status'],
            problematic_timestamps,
            row['report_date']
        ))

    # Commit changes to the database
    conn.commit()


    for (location, cover), subdf in sensor_data_final.groupby(['sensor_location', 'sensor_cover']):
        print(f"Plotting {(location, cover)}")
        
        # Create the first plot: Depth vs DateTime with dual y-axis for RAD and DT
        dt_data = subdf[subdf['sensor_type'] == 'DT']
        rad_data = subdf[subdf['sensor_type'] == 'RAD']

        if not dt_data.empty and not rad_data.empty:
            fig, ax1 = plt.subplots()

            ax1.plot(dt_data['datetime'], dt_data['depth'], 'b-', label='DT Depth')
            ax1.set_xlabel('DateTime')
            ax1.set_ylabel('Depth (DT)', color='b')
            ax1.tick_params('y', colors='b')

            ax2 = ax1.twinx()
            ax2.plot(rad_data['datetime'], rad_data['depth'], 'r-', label='RAD Depth')
            ax2.set_ylabel('Depth (RAD)', color='r')
            ax2.tick_params('y', colors='r')

            plt.title(f'{location} {cover}')
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            fig.autofmt_xdate(rotation=45)
            plt.savefig(f'plots/plot_depth_{location}_{cover}.png', dpi=300)
            plt.close()

        elif not dt_data.empty:
            plt.figure()
            plt.plot(dt_data['datetime'], dt_data['depth'], 'b-', label='DT Depth')
            plt.xlabel('DateTime')
            plt.ylabel('Depth (DT)', color='b')
            plt.title(f'{location} {cover}')
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.gcf().autofmt_xdate(rotation=45)
            plt.savefig(f'plots/plot_depth_{location}_{cover}.png', dpi=300)
            plt.close()

        elif not rad_data.empty:
            plt.figure()
            plt.plot(rad_data['datetime'], rad_data['depth'], 'r-', label='RAD Depth')
            plt.xlabel('DateTime')
            plt.ylabel('Depth (RAD)', color='r')
            plt.title(f'{location} {cover}')
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.gcf().autofmt_xdate(rotation=45)
            plt.savefig(f'plots/plot_depth_{location}_{cover}.png', dpi=300)
            plt.close()
        
        # Add the first plot to a new page in the PDF
        pdf.add_page()
        pdf.image(f'plots/plot_depth_{location}_{cover}.png', x=10, y=10, w=pdf.w - 20)

    # Save PDF
    pdf.output(pdf_output_path)
    print(f"Report saved to {pdf_output_path}")

    ############################################################ END GENERATE DETAILED REPORT ########################################################

