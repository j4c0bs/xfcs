
import csv

# ------------------------------------------------------------------------------
def write_tidy_csv(writer, fcs_objs, meta_keys):
    """Writes tidy / long csv format file.

    Args:
        writer: csv.writer instance
        fcs_objs: iterable of loaded FCSFile instances.
        meta_keys: iterable of fcs metadata Parameter keys to use.

    Returns:
        None
    """

    writer.writerow(meta_keys)
    for fcs in fcs_objs:
        writer.writerow((fcs.param(key) for key in meta_keys))


def write_wide_csv(writer, fcs_objs, meta_keys):
    """Writes wide csv format file.

    Args:
        writer: csv.writer instance
        fcs_objs: iterable of loaded FCSFile instances.
        meta_keys: iterable of fcs metadata Parameter keys to use.

    Returns:
        None
    """

    for key in meta_keys:
        key_row = [key]
        vals = (fcs.param(key) for fcs in fcs_objs)
        key_row.extend(vals)
        writer.writerow(key_row)


def write_file(fcs_objs, meta_keys, csv_fn, tidy):
    """Handles csv.writer init and passing args to selected csv write func.

    Args:
        fcs_objs: iterable of loaded FCSFile instances.
        meta_keys: iterable of fcs metadata Parameter keys to use.
        csv_fn: filepath/name for csv file.
        tidy: bool - enables tidy data format.

    Returns:
        None
    """

    write_csv_file = write_tidy_csv if tidy else write_wide_csv
    with open(csv_fn, 'w') as csv_file:
        writer = csv.writer(csv_file, dialect='excel')
        write_csv_file(writer, fcs_objs, meta_keys)


# ------------------------------------------------------------------------------
def read_file(master_csv, meta_keys):
    """Read in metadata from csv file and determine if format is tidy or wide."""

    merge_keys = []
    merge_data = []
    is_tidy = False

    with open(master_csv, 'r') as metadata_csv:
        meta_reader = csv.reader(metadata_csv)
        rows = [row for row in meta_reader]

    # determine if tidy format
    if len(set(rows[0]) & set(meta_keys)) > 1:
        is_tidy = True
        merge_keys = rows[0]
        for row in rows[1:]:
            merge_data.append({key: value for key, value in zip(merge_keys, row)})

    else:
        # merge_keys = tuple(row[0] for row in rows)
        merge_keys = [row[0] for row in rows]
        if len(set(merge_keys) & set(meta_keys)) > 1:
            entries = len(rows[0])
            for ix in range(1, entries):
                col = (row[ix] for row in rows)
                merge_data.append({key: value for key, value in zip(merge_keys, col)})

    return merge_keys, merge_data, is_tidy


# ------------------------------------------------------------------------------
