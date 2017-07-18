
import argparse
from collections import namedtuple
# from itertools import compress
import os
import sys
import time

from XFCS.FCSFile.FCSFile import FCSFile
from XFCS.utils.locator import locate_fcs_files
from XFCS.version import VERSION
# ------------------------------------------------------------------------------

def parse_arguments():
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(prog='xfcsdata', description='Extract FCS Data')

    fcs_in = parser.add_argument_group('Input Options')
    fcs_in.add_argument(
        '--input', '-i', nargs='+', type=argparse.FileType('rb'), metavar='<file.fcs>',
        help='Optional select input file(s) instead of default directory search.')

    fcs_in.add_argument(
        '--recursive', '-r', action='store_true', dest='recursive',
        help='Enable recursive search of current directory.')

    dsval = parser.add_argument_group('Data Set Options')

    dsval.add_argument('--raw', '-w', action='store_true', help='Raw data values.')
    dsval.add_argument('--channel', '-c', action='store_true', help='Channel data values.')
    dsval.add_argument('--scale', '-s', action='store_true', dest='scale', help='Log scale data values.')
    dsval.add_argument('--xcxs', '-x', action='store_true', help='Log scale values and any non-log channel values.')
    dsval.add_argument('--fl-comp', '-f', action='store_true', dest='fl_comp', help='Fluorescence compensated data values.')
    dsval.add_argument('--scale-fl-comp', '-p', action='store_true', dest='scale_fl_comp', help='Log scaled, fluorescence compensated data values.')

    fcs_out = parser.add_argument_group('Output Options')
    fcs_out.add_argument('--norm-count', '-n', dest='norm_count', action='store_true', help='Normalize event count to start at 1, or forces inclusion in data set if any $PnN=<event count> not located.')
    fcs_out.add_argument('--hdf5', action='store_true', help='Use HDF5 filetype for data instead of csv.')
    fcs_out.add_argument('--metadata', '-m', action='store_true', help='Generate metadata csv file for each fcs file.')
    parser.add_argument('-v', '--version', action='version', version=VERSION)
    return parser.parse_args()


# ------------------------------------------------------------------------------

def store_hdf5_data(data_set, data_desc, filepath):
    # >>> fix names
    data_name = os.path.basename(filepath.rsplit('.', 1)[0])
    data_path = filepath.rsplit('.', 1)[0] + '_{}.h5'.format(data_desc)
    data_set.to_hdf(data_path, data_name, mode='w', complib='zlib', complevel=9)


def store_csv_data(data_set, data_desc, filepath):
    data_path = filepath.rsplit('.', 1)[0] + '_{}.csv'.format(data_desc)
    data_set.to_csv(data_path, index=False)


def batch_export_data(fcs_paths, get_set, hdf, norm_count):

    if hdf:
        store_data = store_hdf5_data
    else:
        store_data = store_csv_data

    for path in fcs_paths:
        fcs = FCSFile()
        fcs.load(path)
        fcs.load_data(norm_count)

        if get_set.raw:
            data_set = fcs.data.raw
            store_data(data_set, 'raw', path)

        if get_set.channel:
            data_set = fcs.data.channel
            store_data(data_set, 'channel', path)

        if get_set.scale:
            data_set = fcs.data.scale
            store_data(data_set, 'scale', path)

        if get_set.xcxs:
            # data_set = fcs.data.xcxs
            data_set = fcs.data.channel_scale
            store_data(data_set, 'xcxs', path)

        if get_set.fl_comp:
            data_set = fcs.data.compensated
            store_data(data_set, 'fl_comp', path)

        if get_set.scale_fl_comp:
            data_set = fcs.data.scale_compensated
            store_data(data_set, 'scale_fl_comp', path)


# ------------------------------------------------------------------------------
# TODO: implement --metadata
# TODO: implement --norm-count
# TODO: sanitize names for hdf5

# ------------------------------------------------------------------------------
def main():
    args = parse_arguments()
    if args.input:
        fcs_paths = [infile.name for infile in args.input if infile.name.lower().endswith('.fcs')]
    else:
        fcs_paths = locate_fcs_files(args.recursive)

    if not fcs_paths:
        print('No fcs files located')
        sys.exit(0)

    set_names = ('raw', 'channel', 'scale', 'xcxs', 'fl_comp', 'scale_fl_comp')
    set_choices = tuple(getattr(args, name) for name in set_names)
    get_set = namedtuple('Get', set_names)

    start = time.perf_counter()

    batch_export_data(fcs_paths, get_set(*set_choices), args.hdf5, args.norm_count)

    end = time.perf_counter() - start
    print('{:.4f} sec'.format(end))

    print()
