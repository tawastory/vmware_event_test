#!/usr/bin/env python

import re
import sys
import datetime
import traceback
import csv

from pyVmomi import vim, vmodl
from pyVim.connect import SmartConnectNoSSL
from pyVim.task import WaitForTask

import psycopg2 as pg2

def read_csv_file(vm_name):
    try:
        with open('target_list.csv', mode='r') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if(row['tobe_vm'] == vm_name):
                    return row['tobe_host']

    except Exception as e:
        print(traceback.print_exc())

def get_connection():
    si = SmartConnectNoSSL(host="vcenter.test.kr",
                           user="administrator@vsphere.local",
                           pwd="Password12#$",
                           port=443)

    return si

def event_callback(event):
    try:
        #print("%s,%s,%s" % (event._wsdlName, event.createdTime, event.fullFormattedMessage))
        #print(event)
        si = get_connection()

        #print(type(event))

        if(type(event) == vim.event.VmPoweredOffEvent):
            # if(event.vm.name == 'test-vm1'):
            msg = "Powered Off VM %s On Host %s" % (event.vm.name, event.host.name)
            print(msg)

            target_name = read_csv_file(event.vm.name)
            print(target_name)
            if target_name is not None:
                content = si.RetrieveContent()
                vm = get_obj(content, [vim.VirtualMachine], event.vm.name)

                #target_name = 'esx1.test.kr'
                destination_host = get_obj(content, [vim.HostSystem], target_name)
                managed_entity = get_obj(content, [vim.ManagedEntity], target_name)
                resource_pool = vm.resourcePool
                migrate_priority = vim.VirtualMachine.MovePriority.defaultPriority

                msg = "Migrating %s to destination host %s" %  (event.vm.name, target_name)
                print(msg)
                task = vm.Migrate(pool=resource_pool, host=destination_host, priority=migrate_priority)
                WaitForTask(task)

                msg = "Power On %s On destination host %s" % (event.vm.name, target_name)
                task = vm.PowerOn()
                WaitForTask(task)

        elif(type(event) == vim.event.VmPoweredOnEvent):
            msg = "Powered On VM %s On Host %s" % (event.vm.name, event.host.name)
            print(msg)

    except Exception as e:
        print(traceback.print_exc())


def get_obj(content, vimtype, name):
    """
     Get the vsphere object associated with a given text name
    """
    obj = None
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj


def wait_for_task(task):
    """ wait for a vCenter task to finish """
    task_done = False
    while not task_done:
        if task.info.state == 'success':
            return task.info.result

        if task.info.state == 'error':
            print("there was an error")
            task_done = True

def main():
#    args = setup_args()

    si = get_connection()

    dc = si.content.rootFolder.childEntity[0]

    ids = ['VmPoweredOnEvent', 'VmPoweredOffEvent']
    byTime = vim.event.EventFilterSpec.ByTime(beginTime=si.CurrentTime())
    byEntity = vim.event.EventFilterSpec.ByEntity(entity=dc, recursion='all')
    filterSpec = vim.event.EventFilterSpec(eventTypeId=ids, time=byTime, entity=byEntity)

    eventCollector = si.content.eventManager.CreateCollector(filterSpec)
    # Keep track of events that are seen as latestPage won't remove them
    # until they have gone out of view.
    seenEvents = set()

    try:
        with PcFilter(eventCollector, ['latestPage']) as pc:
            pc.wait() # Get all the current events from the past.
            while True:
               updt = pc.wait()
               if updt is not None:
                   latestPage = updt.filterSet[0].objectSet[0].changeSet[0].val
                   for event in latestPage:
                       if event.key not in seenEvents:
                           seenEvents.add(event.key)
                           event_callback(event)
    finally:
        eventCollector.Remove()


# Class to simplify the property collector usage.
# Call wait once to generate the initial properties. Subsequent calls will
# wait for updates.
class PcFilter(object):
    def __init__(self, obj, props):
        self.obj = obj
        self.pc = self._get_pc().CreatePropertyCollector()
        self.props = props
        self.pcFilter = None
        self.version = ''

    def __enter__(self):
        PC = vmodl.query.PropertyCollector
        filterSpec = PC.FilterSpec()
        objSpec = PC.ObjectSpec(obj=self.obj)
        filterSpec.objectSet.append(objSpec)
        propSet = PC.PropertySpec(all=False)
        propSet.type = type(self.obj)
        propSet.pathSet = self.props
        filterSpec.propSet = [propSet]
        self.pcFilter = self.pc.CreateFilter(filterSpec, False)
        return self

    def __exit__(self, *args):
        if self.pcFilter is not None:
            self.pcFilter.Destroy()
        if self.pc is not None:
            self.pc.Destroy()

    def wait(self, timeout=None):
        options = vmodl.query.PropertyCollector.WaitOptions()
        options.maxWaitSeconds = timeout
        update = self.pc.WaitForUpdatesEx(self.version, options)
        if update is not None:
            self.version = update.version
        return update

    def _get_si(self):
        return vim.ServiceInstance('ServiceInstance', stub=self.obj._stub)

    def _get_pc(self):
        return self._get_si().content.propertyCollector


if __name__ == '__main__':
    main()