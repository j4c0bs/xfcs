"""
Partial text below copied from NIHMS203250-supplement-Supp_Fig_1:
    International Society for Advancement of Cytometry
    Data File Standard for Flow Cytometry
    Version FCS 3.1 Normative Reference
    Copyright (c) 2008-2009 ISAC

>>> Note: $DATE,$ETIM are optional FCS TEXT segment keywords.

$DATE/dd-mmm-yyyy/ $DATE/01-OCT-1994/
This keyword specifies the date on which the data set was created.
If the beginning and end of data acquisition occur on different dates,
the value of the $DATE keyword should correspond to the beginning of acquisition.
The format is day-month-year with the number of characters specified by dd-mmm-yyyy.
This data set was created on 01 October 1994. Note that the all the character
positions should be filled including leading zeros. Accepted abbreviations for
the months are: JAN, FEB, MAR, APR, MAY, JUN, JUL, AUG, SEP, OCT, NOV, DEC.

>>> Note: test fcs files do not have hyphen delimiters
        e.g. '01 oct 1994'

$ETIM/hh:mm:ss[.cc]/ $ETIM/14:22:10.47/
Clock time at the end of data acquisition. The format of the value is 24-hour
clock hours:minutes:seconds.number of fractional seconds in units of 1/100 of a
second. Data acquisition ended at 14 hours, 22 minutes, 10 seconds, and 47/100
of a second. The fractional seconds keyword value is optional as indicated by
the square brackets.

"""

import datetime
from operator import itemgetter
from os.path import getctime
# ------------------------------------------------------------------------------
def safe_ctime(filepath):
    """Safe access to os.path.getctime.

    Arg:
        filepath

    Returns:
        ctime as float or 0 if system is unable to access file metadata.
    """

    try:
        ctime = getctime(filepath)
    except OSError:
        ctime = 0
    return ctime


def sort_by_ctime(paths):
    """Sorts list of file paths by ctime in ascending order.

    Arg:
        paths: iterable of filepaths.

    Returns:
        list: filepaths sorted by ctime or empty list if ctime is unavailable.
    """

    ctimes = list(map(safe_ctime, paths))
    if not all(ctimes) or len(set(ctimes)) <= 1:
        return []
    else:
        return sorted(paths, key=lambda fp: safe_ctime(fp))


def __all_have_key(fcs_objs, key):
    """Utility func to confirm all fcs objects have a specified parameter key.

    Args:
        fcs_objs: iterable of loaded FCSFile instances.
        key: str parameter key.

    Returns:
        bool: True if all fcs objs have key.
    """

    return all(fcs.has_param(key) for fcs in fcs_objs)


def __get_all(fcs_objs, key):
    """Utility func to retrieve a specified parameter key for all fcs objs.
        Returns values only if all fcs objs have specified key in text map.

    Args:
        fcs_objs: iterable of loaded FCSFile instances.
        key: str parameter key.

    Returns:
        list: fcs param values
    """

    if __all_have_key(fcs_objs, key):
        return [fcs.param(key) for fcs in fcs_objs]
    else:
        return []


def sort_by_time_params(fcs_objs):
    """Uses optional, time related fcs keys ($DATE,$ETIM) to sort iterable.
        If fcs text section does not include either keys, returns empty list.

    Arg:
        fcs_objs: iterable of loaded FCSFile instances.

    Returns:
        iterable of fcs objs sorted by timestamp or empty list.
    """

    meta_dates = __get_all(fcs_objs, '$DATE')
    meta_time = __get_all(fcs_objs, '$ETIM')

    if not any((meta_dates, meta_time)):
        return []

    converted_dates = []
    converted_times = []
    dt_strptime = datetime.datetime.strptime

    if meta_dates:
        prep_date = [date.replace('-', ' ') for date in meta_dates]
        date_fmt = '%d %b %Y'
        converted_dates = [dt_strptime(date, date_fmt) for date in prep_date]
    if meta_time:
        prep_time = [hms.split('.')[0] if '.' in hms else hms for hms in meta_time]
        time_fmt = '%X'
        converted_times = [dt_strptime(hms, time_fmt).time() for hms in prep_time]

    epoc_secs = []
    dt_combine = datetime.datetime.combine

    if converted_dates and converted_times:
        epoc_secs = [dt_combine(dmy, hms).timestamp()
                     for (dmy, hms) in zip(converted_dates, converted_times)]
    elif converted_dates:
        epoc_secs = [dmy.timestamp() for dmy in converted_dates]
    elif converted_times:
        epoc_secs = [hms.timestamp() for hms in converted_times]

    time_fcs = sorted(zip(epoc_secs, fcs_objs), key=itemgetter(0))
    _, sorted_fcs = zip(*time_fcs)
    return sorted_fcs


# ------------------------------------------------------------------------------
