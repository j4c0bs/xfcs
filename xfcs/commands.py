import argparse

from xfcs import get_data, get_metadata
from xfcs.version import VERSION
# ------------------------------------------------------------------------------

def add_global_options(cmd_parser):
    fcs_in = cmd_parser.add_argument_group('Input Options')
    fcs_in.add_argument(
        '--input', '-i', nargs='+', type=argparse.FileType('rb'), metavar='<file.fcs>',
        help='Optional select input file(s) instead of default directory search.')

    fcs_in.add_argument(
        '--recursive', '-r', action='store_true', dest='recursive',
        help='Enable recursive search of current directory.')


def parse_arguments():
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(prog='xfcs', description='Extract FCS Data and Metadata')

    subparsers = parser.add_subparsers(dest='command')
    data = subparsers.add_parser('data')
    data.set_defaults(func=get_data.main)
    add_global_options(data)

    meta = subparsers.add_parser('metadata')
    meta.set_defaults(func=get_metadata.main)
    add_global_options(meta)

    # --------------------------------------------------------------------------
    # DATA ARGS
    # --------------------------------------------------------------------------
    dsval = data.add_argument_group('Data Set Options')

    dsval.add_argument(
        '--raw', '-w', action='store_true', help='Raw data values.')

    dsval.add_argument(
        '--channel', '-c', action='store_true', help='Channel data values.')

    dsval.add_argument(
        '--scale', '-s', action='store_true', dest='scale',
        help='Log scale data values.')

    dsval.add_argument(
        '--xcxs', '-x', action='store_true',
        help='Scale values and any non-scaled channel values.')

    dsval.add_argument(
        '--fl-comp', '-f', action='store_true', dest='fl_comp',
        help='Fluorescence compensated data values.')

    dsval.add_argument(
        '--scale-fl-comp', '-p', action='store_true', dest='scale_fl_comp',
        help='Log scaled, fluorescence compensated data values.')

    fcs_out = data.add_argument_group('Output Options')

    fcs_out.add_argument(
        '--ref-count', '-e', dest='norm_count', action='store_false',
        help='Use actual event count parameter data instead of normalizing start to one.')

    fcs_out.add_argument(
        '--ref-time', '-t', dest='norm_time', action='store_false',
        help='Use actual time parameter data instead of normalizing start to zero.')

    fcs_out.add_argument(
        '--hdf5', action='store_true',
        help='Use HDF5 filetype for data instead of csv.')

    fcs_out.add_argument(
        '--metadata', '-m', action='store_true',
        help='Generate metadata csv file for each fcs file.')

    # --------------------------------------------------------------------------
    # METADATA ARGS
    # --------------------------------------------------------------------------
    csvout = meta.add_argument_group('Output Option - select 1')
    outgrp = csvout.add_mutually_exclusive_group()

    outgrp.add_argument(
        '--sep-files', '-s', action='store_true', dest='sepfiles',
        help='Each input FCS file generates one csv file.')

    outgrp.add_argument(
        '--output', '-o', type=argparse.FileType('w'), metavar='<file.csv>',
        help='Output .csv filepath for merged metadata file.')

    procopt = meta.add_argument_group('Metadata Option - select 1')
    kw_merge = procopt.add_mutually_exclusive_group()

    kw_merge.add_argument(
        '--append-to', '-a', type=argparse.FileType('r'), metavar='<metadata.csv>',
        dest='merge', help='Append fcs metadata to existing fcs metadata csv file.')

    kw_merge.add_argument(
        '--spx-names', '-n', action='store_true', dest='spx_names',
        help='Filter output to only include $PxN channel names.')

    kw_merge.add_argument(
        '--kw-filter', '-k', type=argparse.FileType('r'), metavar='<user_kw.txt>',
        dest='kw_filter', help='Filter output with USER KeyWord preferences file.')

    kw_merge.add_argument(
        '--get-kw', '-g', action='store_true', dest='get_kw',
        help='Generate user keyword text file.')

    meta.add_argument(
        '--limit', '-l', type=int, default=0, metavar='n',
        help='Number of most recent files to parse.')

    meta.add_argument(
        '--thirdnormal', '-t', action='store_true', dest='tidy',
        help='Outputs CSV in third normal form (long).')

    meta.add_argument(
        '--dashboard', action='store_true',
        help='Generate interactive plot with current metadata scan.')

    meta.add_argument(
        '-q', '--quiet', action='store_true',
        help='Disable fcs load notification.')

    # --------------------------------------------------------------------------
    parser.add_argument('-v', '--version', action='version', version=VERSION)

    return parser.parse_args()


# ------------------------------------------------------------------------------
def main():
    args = parse_arguments()
    args.func(args)


# ------------------------------------------------------------------------------
