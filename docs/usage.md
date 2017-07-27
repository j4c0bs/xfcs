## xfcs Usage:
------------------------------------------------
### File input:
With no input files entered, the current directory will be searched for fcs files. Applies to both data and metadata.
1. Recursive search:
Enables recursive search of current directory.
    --recursive, -r
2. List input files:
Optional select input file(s) instead of default directory search.
    --input, -i file1.fcs file3.fcs

------------------------------------------------
### Extract Data:
    xfcsdata [--options]

All data sets are written to their own, separate file and named based on their source FCS file and the type of set. Default output is csv file in tidy format with parameter names as column names.

##### Data Set Options:
Extracted data sets include all parameters relative to the specified transform. Except for raw output, time and event count data is included to all data sets. Any number of the options below can be enabled within the same command. If a file does not have parameters which apply to a requested data set, a notice will be displayed and other applicable data sets will be extracted.

Commands can be combined using their short version and each data set will still generate their own file.
    e.g. extract raw, channel, and scale values
    xfcsdata -wcs

1. Raw:
Parameter data extracted with no scaling, transforms or bit masks applied.
    --raw, -w
2. Channel:
Raw data with bit masks, if applicable. Time is normalized to start at 0 (unless --ref-time enabled).
Event count is normalized if it exists (unless --ref-count enabled) or it is automatically added.
    --channel, -c
3. Scale:
Includes only parameters with a log10 or gain scale applied.
Event count and time automatically included.
    --scale, -s
4. Channel Scale (xcxs):
Includes any parameter channel values that do not have a scale value, all parameter scale values.
Event count and time automatically included.
    --xcxs, -x
5. Fluorescence Compensated:
Parameters located in $SPILLOVER matrix and their compensated channel values. Event count and time automatically included.
    --fl-comp, -f
6. Scaled Fluorescence Compensated:
Any parameter with both compensation and log10 scaling. Log scaling is applied to fluorescence compensated values. Event count and time automatically included.
    --scale-fl-comp, -p

##### Time and Event Count Options:
1. Use actual event count parameter data (if it exists) instead of normalizing start to one.
    --ref-count, -e
2. Use actual time parameter data (if it exists) instead of normalizing start to zero.
    --ref-time, -t

##### Output Options:
1. Output defaults to csv file. To use HDF5 instead:
    --hdf5
2. Automatically generate metadata csv file for each fcs file.
    --metadata, -m

------------------------------------------------
### Extract Metadata:
    xfcsmeta [--options]

Extracts all header and text section keyword, value pairs and writes content to csv file. Multiple FCS files can be written to the same csv file regardless of shared keywords. Default format is wide.

##### Third normal form (long, tidy):
Outputs CSV in long format where each row is one fcs file.
    --tidy, -t

##### Additional Input Option:
Limit input to n number of most recent files.
  --limit n, -l n

##### Output Option - select 1:
Default behavior is for all FCS files to be included within the same csv file and named based the current directory. One of the 2 options below can be selected to enable either separate metadata files per FCS file, or specified filename and filepath for the default merged csv file.
1. Each input FCS file generates one csv file.
    --sep-files, -s
2. Designate the output .csv filepath for merged, default metadata file.
    --output <file.csv>, -o <file.csv>

##### Keyword Metadata Option - select 1:
1. Generate user keyword text file containing all keywords located within all FCS files scanned. Necessary for utilizing Keyword filtering and statistics. Generates <FCS_USER_KW.txt> within current directory.
    --get-kw, -g

2. Filter text section keyword values to create custom metadata output. Remove any unwanted keywords from FCS_USER_KW.txt and enter path in command like below. Additional numeric keyword statistics described at the end.
    --kw-filter <user_kw.txt>, -k <user_kw.txt>

3. Append new FCS metadata to existing FCS metadata csv file. Keywords used in existing metadata file will act as a filter for new FCS files.
    --append-to <metadata_filepath.csv>, -a <metadata_filepath.csv>

##### Metadata Numeric Keyword Mean:
Using the FCS_USER_KW.txt file, a numeric keyword can have a rolling mean column added to metadata output. Default historic mean range is 10 but can be customized. Appending MEAN to any keyword will enable this feature.

Example keyword: $P25V
- enable mean column
    $P25V_MEAN
- enable mean column with history of 5 last values
    $P25V_MEAN_5
