## XFCS metadata workflow:
--------------------------------------------------------------------------------

### Keyword Filter:
--------------------------------------------------------------------------------

1. Run an initial extraction on one fcs file to view all keyword, value pairs:

        xfcs metadata -i fcsfile1.fcs

2. Generate keyword only text file which will be edited and used to filter the final scan:

        xfcs metadata -i fcsfile1.fcs -g

3. Open FCS_USER_KW.txt in your preferred text editor and remove unwanted keywords.
    * Change the text file name to your preference.
    * The keyword order within the file will be mirrored in the filtered csv file.

4. Extract metadata and apply the keyword filter:

        xfcs metadata -k FCS_USER_KW.txt -o fcs_filtered_metadata.csv


__Tips:__
* The generated metadata csv file will use the current directory's name for all extractions. There is no overwrite protection built in. To prevent file overwrite, use the `--output`, `-o` option to specify a name for the csv file.
* If the metadata files will be stored without the original fcs files, save a copy of the complete metadata extraction with no keyword filters enabled.


--------------------------------------------------------------------------------
### Mean Values:
--------------------------------------------------------------------------------

Using the `FCS_USER_KW.txt` file, a numeric keyword can have a rolling mean column added to metadata output. Default historic mean range is 10 but can be specified. If used in combination with the add-on module xfcsdashboard, parameter mean values will be grouped with their source for easy comparison.  

1. Follow steps 1-3 above.

2. Any keyword can have a mean value included using the following format within the `FCS_USER_KW.txt` file:

        example keyword: $TOT

    Include mean with rolling history of last N values:

    ```
    $TOT_MEAN_N
    ```

    As seen within the text file using a rolling history of 5 last values:

    ```
    $TOT
    $TOT_MEAN_5
    ```

3. If you are including a __channel parameter__ such as $P4V or $P4G, read the steps below carefully.

    * If you are tracking values from multiple machine configurations, the parameter id numbers are not necessarily standardized. The keyword mean values are calculated by matching the actual keyword between different fcs files.

    * For example: $P4N is __FS Lin__ in a specific machine configuration. But, after disabling or enabling other color channels $P4N now refers to __SS Area__. Tracking the voltage of $P4V will provide invalid results as it includes data for 2 different channels.

    * Determine the channel names for current parameter id numbers.
        This information can be found within a metadata file or quickly located by using the following command:

        ```
        xfcs metadata --spx-names
        ```

    * Edit your keyword prefs text file and include any mean values using the specific channel attribute (replacing the channel id number with x), channel name, and MEAN keyword with rolling history value.

    * Using the example above, the following line would track __FS Lin__ values for voltage regardless of the channel id number:

        ```
        $PxV_FSLIN_MEAN_10
        ```



4. Extract metadata and apply the keyword filter:

    ```
    xfcs metadata -k FCS_USER_KW.txt -o fcs_mean_metadata.csv
    ```

--------------------------------------------------------------------------------
