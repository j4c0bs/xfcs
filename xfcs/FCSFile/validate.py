"""
All functions related to:
    - validating fcs header and text section conforms to file format specifications
    - confirming input fcs file is supported for data extraction
"""

from itertools import compress
import warnings
from .FCSError import BytesReadLengthError, BytesWordLengthError, FormatNotSupportedError, RequiredKeywordsError
# ------------------------------------------------------------------------------

def has_correct_word_len(datatype, word_len):

    status = False
    bad_len = 0
    if datatype == 'F' and word_len != 32:
        bad_len = word_len
    elif datatype == 'D' and word_len != 64:
        bad_len = word_len
    elif datatype == 'I' and word_len % 8 != 0:
        bad_len = word_len
    else:
        status = True

    if not status:
        raise BytesWordLengthError(datatype, word_len)


def is_list_mode(mode):
    if mode != 'L':
        raise NotImplementedError('FCS file type: {} is not supported.'.format(mode))


def is_supported_datatype(datatype):
    if datatype not in ('I', 'F', 'D'):
        raise FormatNotSupportedError(datatype)


def has_correct_read_length(data_len, enddata, begindata):
    header_read_len = enddata - begindata
    if abs(data_len - header_read_len) > 1:
        raise BytesReadLengthError(data_len, header_read_len)


def has_one_data_set(nextdata):
    if nextdata != 0:
        message = 'FCS file contains > 1 data set. Only the first set will be extracted.'
        warnings.warn(message, RuntimeWarning, stacklevel=2)


def file_format(text, spec):
    is_list_mode(text['$MODE'])
    is_supported_datatype(spec.datatype)
    has_correct_word_len(spec.datatype, spec.word_len)
    has_correct_read_length(spec.data_len, spec.enddata, spec.begindata)
    has_one_data_set(text.get('$NEXTDATA', 0))
    return True


def file_mode_type(text):
    return text['$MODE'] == 'L' and text['$DATATYPE'] in ('I', 'F', 'D')


# ------------------------------------------------------------------------------
def required_keywords(text):
    status = False

    keywords = [
        '$BEGINANALYSIS', '$BEGINDATA', '$BEGINSTEXT', '$BYTEORD',
        '$DATATYPE', '$ENDANALYSIS', '$ENDDATA', '$ENDSTEXT', '$MODE',
        '$NEXTDATA', '$PAR', '$TOT']

    all_spx_params = []
    n_params = text.get('$PAR', 0)
    req_attr = ('B', 'E', 'N', 'R')
    for ix in range(1, n_params + 1):
        spx_ = '$P{}'.format(ix)
        all_spx_params.extend((spx_ + attr for attr in req_attr))

    keywords.extend(all_spx_params)
    required_keywords = tuple(kw in text for kw in keywords)


    if not all(required_keywords):
        missing_keywords = tuple(compress(keywords, required_keywords))
        raise RequiredKeywordsError(missing_keywords)
    else:
        status = True

    return status


# ------------------------------------------------------------------------------
