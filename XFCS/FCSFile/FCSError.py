"""
Custom FCS file exceptions
"""

class FCSError(Exception):
    """Base class for all fcs exceptions"""
    pass


class FileNotLoadedError(FCSError):
    """Error to be raised when """

    def __str__(self):
        return 'FCS File must be loaded before accessing data'


class BytesWordLengthError(FCSError):
    """Error to be raised when fcs file has unsupported format

    Attributes:

    datatype
        File format data type (I, F, D)
    bad_len
        Word length (bits) located in text section
    """

    def __init__(self, datatype, bad_len):
        self.datatype = datatype
        self.bad_len = bad_len

    def __str__(self):
        return 'FCS datatype ({}) has incorrect word length of {} bits'.format(datatype, bad_len)


class BytesReadLengthError(FCSError):
    """Error to be raised when fcs file has unsupported format

    Attributes:

    data_len
        Calculated length of data based on number of params * total events
    header_read_len
        Byte read length supplied in text section
    """

    def __init__(self, data_len, header_read_len):
        self.datatype = datatype
        self.bad_len = bad_len

    def __str__(self):
        return 'Calculated byte read length ({}) does not match length in text section ({})'.format(data_len, header_read_len)


class FormatNotSupportedError(FCSError):
    """Error to be raised when fcs file has unsupported format

    Attributes:

    details
        File format details
    """

    def __init__(self, details):
        # super().__init__(details)
        self.details = details

    def __str__(self):
        return 'FCS file format type: {} is not supported for data extraction'.format(self.details)


class RequiredKeywordsError(FCSError):
    """Error to be raised when required parameter keywords are not found

    Attributes:

    missing_keywords
        The missing parameter keywords
    """

    def __init__(self, missing_keywords):
        # super().__init__(missing_keywords)
        self.missing_keywords = missing_keywords

    def __str__(self):
        return 'FCS parameter keywords are missing: {}'.format(self.missing_keywords)
