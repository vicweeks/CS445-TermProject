from datetime import datetime
import time
import os
from gw2spidy import Gw2Spidy as spidy # allows retrieval of market information
import numpy as np

from apscheduler.schedulers.background import BackgroundScheduler

itemIDs = (19718,19720,19697,19680,19719,19738,19723,19710,
           19739,19740,19699,19683,19703,19687,19728,19733,19726,19713,
           19741,19742,19698,19682,19730,19734,19727,19714,
           19743,19744,19702,19686,19731,19736,19736,19724,19711,
           19748,19747,19700,19684,19729,19735,19722,19709,
           19745,19746,19701,19685,19732,19737,19725,19712)

# This function adds current timepoint data to previous data and saves it
def saveItemTimepoint():
    now = datetime.now()
    allItems = np.load('itemData.npy')
    for id in itemIDs:
        item = spidy.getItemData(id)
        itemData = [item['data_id'], item['max_offer_unit_price'], item['min_sale_unit_price'], item['offer_availability'], item['sale_availability'], item['sale_price_change_last_hour'], item['offer_price_change_last_hour'],
                   now.year, now.month, now.day, now.hour, now.minute, now.second]
        allItems = np.vstack((allItems, itemData))
    np.save('itemData', allItems)
    print('Saved item data at: %s' % datetime.now())


if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(saveItemTimepoint, 'interval', minutes=15)
    scheduler.start()
    print('Kill the kernel to stop.')

    try:
        # This is here to simulate application activity (which keeps the main thread alive).
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        # Not strictly necessary if daemonic mode is enabled but should be done if possible
        scheduler.shutdown()