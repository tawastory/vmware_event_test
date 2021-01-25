#!/usr/bin/env python
import re
import sys
from datetime import datetime, timedelta
import traceback
import psycopg2 as pg2

from pyVmomi import vim
from pyVim.connect import SmartConnectNoSSL
from pyVim.task import WaitForTask

def main():
        si = SmartConnectNoSSL(host="vcenter.test.kr",user="administrator@vsphere.local",pwd="Password12#$",port=443)
        dc = si.content.rootFolder.childEntity[0]

#   byId = ['HostConnectionLostEvent']
        byId = []
        byTime = vim.event.EventFilterSpec.ByTime()
        now = datetime.now()
        byTime.beginTime = now - timedelta(hours=1)
        byTime.endTime = now

        byEntity = vim.event.EventFilterSpec.ByEntity(entity=dc, recursion='all')
        filterSpec = vim.event.EventFilterSpec(eventTypeId=byId, time=byTime, entity=byEntity)

        eventManager = si.content.eventManager
        events = eventManager.QueryEvent(filterSpec)

        #print("%s" % events)

        try:
                conn = pg2.connect(dbname='test', user='postgres', password='postgres', host='localhost')
                cur = conn.cursor()

                for event in events:
                        print ("%s %s %s" % (event._wsdlName,event.createdTime,event.fullFormattedMessage))

                        query = "INSERT INTO vmware_events(date, eventId, message) VALUES ("
                        query = query + "'" + str(event.createdTime) + "',"
                        query = query + "'" + event._wsdlName + "',"
                        message = event.fullFormattedMessage.replace("'","")
                        query = query + "'" + message + "'" + ")"
                        #print query

                        cur.execute(query)
                        conn.commit()

        except Exception as e:
                print (traceback.print_exc())

        if conn:
                conn.close()

if __name__ == '__main__':
    main()