from __future__ import print_function
from pyVim.connect import SmartConnectNoSSL, Disconnect
from pyVmomi import vim
import atexit
import sys


def GetVMHosts(content):
    print("Getting all ESX hosts ...")
    host_view = content.viewManager.CreateContainerView(content.rootFolder,
                                                        [vim.HostSystem],
                                                        True)
    obj = [host for host in host_view.view]
    host_view.Destroy()
    return obj


def GetVMs(content):
    print("Getting all VMs ...")
    vm_view = content.viewManager.CreateContainerView(content.rootFolder,
                                                      [vim.VirtualMachine],
                                                      True)
    obj = [vm for vm in vm_view.view]
    vm_view.Destroy()
    return obj


def GetHostsPortgroups(hosts):
    print("Collecting portgroups on all hosts. This may take a while ...")
    hostPgDict = {}
    for host in hosts:
        pgs = host.config.network.portgroup
        hostPgDict[host] = pgs
        print("\tHost {} done.".format(host.name))
    print("\tPortgroup collection complete.")
    return hostPgDict


def PrintVmInfo(vm):
    vmPowerState = vm.runtime.powerState
    print("Found VM:", vm.name + "(" + vmPowerState + ")")
    GetVMNics(vm)


def GetVMNics(vm):
    for dev in vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualEthernetCard):
            dev_backing = dev.backing
            portGroup = None
            vlanId = None
            vSwitch = None
            if hasattr(dev_backing, 'port'):
                portGroupKey = dev.backing.port.portgroupKey
                dvsUuid = dev.backing.port.switchUuid
                try:
                    dvs = content.dvSwitchManager.QueryDvsByUuid(dvsUuid)
                except:
                    portGroup = "** Error: DVS not found **"
                    vlanId = "NA"
                    vSwitch = "NA"
                else:
                    pgObj = dvs.LookupDvPortGroup(portGroupKey)
                    portGroup = pgObj.config.name
                    vlanId = str(pgObj.config.defaultPortConfig.vlan.vlanId)
                    vSwitch = str(dvs.name)
            else:
                portGroup = dev.backing.network.name
                vmHost = vm.runtime.host
                # global variable hosts is a list, not a dict
                host_pos = hosts.index(vmHost)
                viewHost = hosts[host_pos]
                # global variable hostPgDict stores portgroups per host
                pgs = hostPgDict[viewHost]
                for p in pgs:
                    if portGroup in p.key:
                        vlanId = str(p.spec.vlanId)
                        vSwitch = str(p.spec.vswitchName)
            if portGroup is None:
                portGroup = 'NA'
            if vlanId is None:
                vlanId = 'NA'
            if vSwitch is None:
                vSwitch = 'NA'
            print('\t' + dev.deviceInfo.label + '->' + dev.macAddress +
                  ' @ ' + vSwitch + '->' + portGroup +
                  ' (VLAN ' + vlanId + ')')

def main():
    global content, hosts, hostPgDict
    serviceInstance = SmartConnectNoSSL(host="vcenter.test.kr",user="administrator@vsphere.local",pwd="Password12#$",port=443)
    atexit.register(Disconnect, serviceInstance)
    content = serviceInstance.RetrieveContent()
    hosts = GetVMHosts(content)
    hostPgDict = GetHostsPortgroups(hosts)
    vms = GetVMs(content)
    for vm in vms:
        PrintVmInfo(vm)

# Main section
if __name__ == "__main__":
    sys.exit(main())