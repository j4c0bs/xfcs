
try:
    import xfcsdashboard
    STATUS = ''
    DASHBOARD = True

except ImportError as e:
    STATUS = e
    DASHBOARD = False


def dashboard(fcs_objs, meta_keys):
    if DASHBOARD:
        xfcsdashboard.dashboard.plot_data(fcs_objs, meta_keys)
    else:
        print('>>>', STATUS)
        print('>>> Unable to generate dashboard plot. Install xfcsdashboard.')
