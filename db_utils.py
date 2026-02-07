import os
import sqlalchemy
import pandas as pd
import time

def connect_to_images_with_proxy(cloud_proxy_path):
    '''
    Connect to the images database 

    Args:
        cloud_proxy_path (str): Path to cloud_proxy.sh

    Return:
        engine (obj): SQL connection engine 
    '''
    # Database credentials and settings
    db_user = 'dataprep'
    db_pass = 'sdK77:+,^^g[+rbV'
    db_name = 'images'
    db_ip   = '127.0.0.1:2235'  # Corrected IP address

    # Connection URL
    URL = f'mysql+pymysql://{db_user}:{db_pass}@{db_ip}/{db_name}'

    # Create the SQLAlchemy engine
    os.system(f'bash {cloud_proxy_path}')
    engine = sqlalchemy.create_engine(URL, pool_size=5, max_overflow=2, 
                            pool_timeout=30, pool_recycle=1800)

    return engine

def read_dataset_from_table(table_name, dataset_name, cloud_proxy_path, ATTEMPT_CAP = 5):
    '''
    From the selected database, return all rows in the selected table and dataset.

    Args:
        table_name (str):       Name of table in the database 
        dataset_name (str):     Value for the 'dataset' column in the database 
        cloud_proxy_path (str): Path to cloud_proxy.sh
        ATTEMPT_CAP (int):      Number of upload attempts to try before aborting 

    Return:
        pd.DataFrame:           All rows in the selected table 
    '''
    # Create the SQLAlchemy engine
    # engine = connect_without_proxy(db_name, instance_name)
    engine = connect_to_images_with_proxy(cloud_proxy_path)

    # Query all rows
    query = f'SELECT * FROM images.{table_name}'
    query += f' WHERE dataset_name = "{dataset_name}"'

    # Connect to database 
    num_attempts = 0
    while 1:
        num_attempts += 1
        try:
            df = pd.read_sql(query, con=engine)
            break
        except Exception as e:
            print(e)
            print(f'Error: Unable to connect to SQL. Trying again...')
            time.sleep(2)
            if num_attempts > ATTEMPT_CAP:
                print(f"Exceeded {ATTEMPT_CAP} attempts, aborting.")
                break

    return df