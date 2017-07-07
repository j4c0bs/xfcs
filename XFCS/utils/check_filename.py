import fnmatch
import os
# ------------------------------------------------------------------------------

def valid_filename(name, type_):
    matches = []
    search_str = '{}*.{}'.format(name, type_)


    for file_ in os.listdir():
        if fnmatch.fnmatch(file_, search_str):
            matches.append(file_)

    valid_name = '{}.{}'.format(name, type_)

    if matches:
        matches.sort(reverse=True)
        last_name = matches[0].split('.')[0]
        if '-' in last_name:
            digits = last_name.rsplit('-', 1)[1]
            try:
                end_digits = int(digits)
            except ValueError:
                end_digits = 'x-0'

            valid_name = '{}-{}.{}'.format(name, end_digits, type_)
        else:
            if name == last_name:
                valid_name = '{}-{}.{}'.format(name, 1, type_)

    return valid_name


# fn_incremented = re.compile(r"^%s\-(\d+)\.%s$" % (name, type_))
