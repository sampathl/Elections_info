# a python script to combine all csv files in a directory into one csv file and save it in the same directory.
import os
import glob
import pandas as pd
os.chdir("static/constituency_candidates_dump/data")
extension = 'csv'
all_filenames = [i for i in glob.glob('*.{}'.format(extension))]
#combine all files in the list ignore the header


combined_csv = pd.concat([pd.read_csv(f) for f in all_filenames ])
#export to csv
combined_csv.to_csv( "combined_csv.csv", index=False, encoding='utf-8-sig')
print("done")
