import argparse
import ipaddress
import keyboard
import pickle
import psutil
import requests
import socket
import time
import os
from datetime import datetime

# the number of days before a requery is necessary to update cache entries
g_requery_in_days = 3

# global quit flag for kb termination
g_quit_flag = False

# the default refresh interval between cycles (using seconds)
g_refresh_interval = 10

# network utilities
class NetworkUtils:
    @staticmethod
    def get_geolocation(ip, token = '', is_commerial = True):
        headers = {'User-Agent': 'NLabs.Studio Netmonitor Snapshot'}
        try:            
            api_url = f"https://ipinfo.io/{ip}/json"
            if len(token) > 0:
                api_url = f"https://ipinfo.io/{ip}/json?token={token}"
            response = requests.get(api_url, headers=headers)
            data = response.json()
            if is_commerial:
                return None

            # fall back option if rate limit has been exceeded 
            # the end-user has specified a non-commercial use case 
            # exists
            if 'error' in data:
                api_url = f"http://ip-api.com/json/{ip}?fields=country,regionName,city,lat,lon,isp,query"
                response = requests.get(api_url, headers=headers)
                data = response.json()
                if 'lat' in data:
                    data['loc'] = data['lat']+','+data['lon']
                    data['ip'] = data['query']
                    data['region'] = data['regionName']
                    data['hostname'] = data['isp']
            return data
        except:
            return None
    @staticmethod
    def is_internal(ip):
        try:
            ip_obj = ipaddress.ip_address(ip)
            if isinstance(ip_obj, ipaddress.IPv4Address):
                return ip_obj.is_private
            elif isinstance(ip_obj, ipaddress.IPv6Address):
                if ip_obj.is_link_local or ip_obj.is_private:
                    return True
                return False
        except:
            return False
    @staticmethod
    def reverse_dns(ip):
        try:
            hn, _, _ = socket.gethostbyaddr(ip)
            return hn
        except socket.herror:
            return None

# network ip address information
class IP_AddressInfo:
    def __init__(self, ip_addr, hostname, city, region, country, location):
        self._ip_addr = ip_addr
        self._hostname = hostname
        self._city = city
        self._region = region
        self._country = country
        self._location = location
        self._log_time = time.time()
    def __str__(self):
        return self._ip_addr +','+ self._hostname +',' + self._city + ','+ self._region + ',' + self._country +',' + self._location
    def ipAddress(self):
        return self._ip_addr
    def hostname(self):
        return self._hostname
    def city(self):
        return self._city
    def region(self):
        return self._region
    def country(self):
        return self._country
    def location(self):
        return self._location
    def logTime(self):
        return self._log_time

# report writer
class ReportWriter:
    # cl - dictionary of SocketConnection objects
    # il - dictionary of IP_AddressInfo objects
    # mr - (optional) produce multiple document reports
    @staticmethod
    def write(cl, il, mr = False):

        date_t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filepath_t = 'report.htm' if not mr else date_t.replace(':', '_').replace('-', '_') + '_report.htm'

        f = open(filepath_t, 'w', encoding='utf-8')
        f.write("<html>")
        f.write("<head>")

        if not mr:
            f.write('<meta http-equiv="refresh" content="'+str(g_refresh_interval)+'; url=nlabs.studio_report.htm">')

        f.write("<title>Netmonitor Snapshot Report</title>")
        f.write('<style type="text/css">')
        f.write("body{margin:0;padding:20px 0px 0px 20px;background-color:#000000;color:#ffffff;font-size:13px;}")
        f.write("h1{font-size:20px;padding:0;margin:0;color:#ffffff;}")
        f.write("p{font-size:20px;margin:0px;padding:0px;}")
        f.write("th{cursor:pointer;}")
        f.write(".mt{margin-top:10px;}")
        f.write("</style>")
        f.write('<script type="text/javascript">')
        f.write("var gcv = function(tr, idx){ return tr.children[idx].innerText || tr.children[idx].textContent; };var c = function(idx, asc) { return function(a, b) { return function(v1, v2) {return v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2) ? v1 - v2 : v1.toString().localeCompare(v2);}(gcv(asc ? a : b, idx), gcv(asc ? b : a, idx));}};window.onload = function(){Array.prototype.slice.call(document.querySelectorAll('th')).forEach(function(th) { th.addEventListener('click', function() {var table = th.parentNode;while(table.tagName.toUpperCase() != 'TABLE') table = table.parentNode;Array.prototype.slice.call(table.querySelectorAll('tr:nth-child(n+2)')).sort(c(Array.prototype.slice.call(th.parentNode.children).indexOf(th), this.asc = !this.asc)).forEach(function(tr) { table.appendChild(tr) });})});};")
        f.write("</script>")
        f.write("</head>")
        f.write("<body>")
        f.write('<table id="data_table">')
        f.write('<tr valign="top" cellspacing="10">')
        f.write('<td><h1>Netmonitor Snapshot Report</h1><p class="mt">Autonomous network monitoring reports for TCP/UDP connections active on the (NIC) network interface card.</p></td>')
        f.write("</tr>")
        f.write("</table>")
        f.write("<br />")
        f.write("<p>Report produced at "+ date_t +" with "+ str(len(cl)) +" connections and "+ str(len(il)) +" entries in cache</p>")
        f.write('<table cellspacing="10">')
        f.write("<tr>")
        f.write('<th align="left">Local</th>')
        f.write('<th align="left">Remote</th>')
        f.write('<th align="left">Type</th>')
        f.write('<th align="left">Time</th>')
        f.write('<th align="left">State</th>')        
        f.write('<th align="left">City</th>')
        f.write('<th align="left">Region</th>')
        f.write('<th align="left">Country</th>')
        f.write('<th align="left">Lat &amp; Long</th>')
        f.write('<th align="left">Hostname</th>')        
        f.write("</tr>")

        for key, c in cl.items():

            i = il[key]

            f.write("<tr>")
            f.write('<td><span style="color:#F5428A;">'+ c.localIP() +"</span>:"+ str(c.localPort()) +"</td>")
            f.write('<td><span style="color:#F5428A;">'+ c.remoteIP() +"</span>:"+ str(c.remotePort()) +"</td>")

            ctype = 'TCP/IP'
            if str(c.connectionType()) == 'SocketKind.SOCK_DGRAM':
                ctype = 'UDP/IP'
            f.write("<td>"+ ctype +"</td>")

            dt = datetime.fromtimestamp(c.time())
            f.write("<td>"+ dt.strftime('%Y-%m-%d %H:%M:%S') +"</td>")

            f.write("<td>"+ c.status() +"</td>")            
            f.write("<td>"+ i.city() +"</td>")
            f.write("<td>"+ i.region() +"</td>")
            f.write("<td>"+ i.country() +"</td>")
            f.write("<td>"+ i.location() +"</td>")
            f.write("<td>"+ i.hostname() +"</td>")
            f.write("</tr>")

        f.write("</table>")
        f.write("</body>")
        f.write("</html>")
        f.close()

# socket connection
class SocketConnection:
    def __init__(self, local_ip, local_port, remote_ip, remote_port, conn_type, status):
        self.local_ip = local_ip
        self.local_port = int(local_port)
        self.remote_ip = remote_ip
        self.remote_port = int(remote_port)
        self.conn_type = conn_type
        self.conn_status = status
        self.log_time =time.time()
    def __str__(self):
        return self.conn_status +' '+ self.local_ip + ':' + str(self.local_port) +' '+ self.remote_ip + ':' + str(self.remote_port) +'           '
    def connectionType(self):
        return self.conn_type
    def isExternal(self):
        return not self.isInternal()
    def isInternal(self):
        return NetworkUtils.is_internal(self.remote_ip)
    def localIPAddr(self):
        return self.local_ip + ':' + str(self.local_port)
    def remoteIPAddr(self):
        return self.remote_ip + ':' + str(self.remote_port)
    def localIP(self):
        return self.local_ip
    def localPort(self):
        return self.local_port
    def remoteIP(self):
        return self.remote_ip
    def remotePort(self):
        return self.remote_port
    def status(self):
        return self.conn_status
    def time(self):
        return self.log_time

def main():

    parser = argparse.ArgumentParser(description="Netmonitor Snapshot - Produce a report of TCP/UDP connections active on the (NIC) network interface card.")
    parser.add_argument('-m', type=int, required=False, help='number of minutes to sleep between each cycle - rate limit')
    parser.add_argument('-t', type=str, required=False, help='hexadecimal basic auth token for ipinfo.io API access with increased rate limit usage')
    parser.add_argument('-f', type=str, required=False, help='flag as non commercial - include the use of free to access non commercial suppliers')
    parser.add_argument('-x', type=str, required=False, help='flush the ip address information cache and export its contents to a CSV file')
    parser.add_argument('-mr', type=str, required=False, help='flag to produce multiple html report documents')
    parser.add_argument('-r', type=int, required=False, default=10, help='override the default refresh rate between cycles')
    parser.add_argument('-sp', type=str, help='perform a single connection sweep and terminate once complete')
    args = parser.parse_args()

    # perform a flush on the IP_AddressInfo cache
    if args.x:
        if os.path.isfile('info_cache'):
            try:
                cache_data = {}
                with open('info_cache', 'rb') as data_t:
                    cache_data = pickle.load(data_t)
                with open('ip_address_info', 'w') as f:
                    for key, c in cache_data.items():
                        f.write(str(c) +"\n")
                os.remove('info_cache')
                print('OK -> flush successful')
            except:
                print('processing error occurred')
        else:
            print('cache data file does not exist')
        return

    # multiple report flag
    mr = args.mr and args.mr.lower() == 'true'

    # not-commercial flag
    nc = args.f and args.f.lower() == 'true'

    # change the default refresh rate between cycles
    global g_refresh_interval
    g_refresh_interval = 10 if not args.r else args.r

    print("Netmonitor Snapshot Report Writer")
    print("CTRL+Q will terminate the process and return you to the command line prompt\n")
    time.sleep(5)

    while not g_quit_flag:

        live_list = psutil.net_connections()
        conn_list = {}

        # info list accomodates our geolocation cache data, if we have actively
        # ran our script before, we may have cache data available which reduces
        # the load on our third party suppliers 
        # 
        # each record is stored for g_requery_in_days before forced update
        info_list = {}
        if os.path.isfile('info_cache'):
            try:
                with open('info_cache', 'rb') as data_t:
                    info_list = pickle.load(data_t)
            except:
                info_list = {}

        # foreach connection
        for c in live_list:

            # check for quit flag
            if g_quit_flag:
                break

            # skip if a remote host has not been ACKnowledged
            if not c.raddr:
                continue
            raddr = f"{c.raddr.ip}:{c.raddr.port}"

            # skip if remote connection is indeed internal on the LAN or a NAT proxy
            if NetworkUtils.is_internal(c.raddr.ip):
                continue

            # record connection
            conn_list[raddr] = SocketConnection(c.laddr.ip, c.laddr.port, c.raddr.ip, c.raddr.port, c.type, c.status)

            # determine if a requery is necessary to update the cache record
            requery = False
            if raddr in info_list:
                requery = info_list[raddr].logTime() < (time.time() - (g_requery_in_days * 86400))

            # no cache record exists or its time for a requery
            if raddr not in info_list or requery:

                # fetch geolocation data
                data_t = NetworkUtils.get_geolocation(c.raddr.ip, '' if not args.t else args.t, not nc)

                # if the third party supplier failed but we have a past 
                # record then we skip overwritting the cached entry
                fallback_on_past_record = data_t == None and requery
                if not fallback_on_past_record:

                    # third party fetch failed... init some defaults
                    if data_t == None:
                        data_t = {}
                        data_t['ip'] = conn_list[raddr].remoteIP()
                        data_t['city'] = data_t['region'] = data_t['country'] = '*'

                    # check hostname is available from third party, if not attempt to query it using a local socket
                    if 'hostname' not in data_t:
                        data_t['hostname'] = NetworkUtils.reverse_dns(c.raddr.ip)
                        if data_t['hostname'] == None:
                            data_t['hostname'] = 'NA'

                    # if longitude/latitude are not available, flag as '*'
                    if 'loc' not in data_t:
                        data_t['loc'] = '*'

                    # cache the geolocation data record
                    info_list[raddr] = IP_AddressInfo(data_t['ip'], data_t['hostname'], data_t['city'], data_t['region'], data_t['country'], data_t['loc'])

            # some console noise - basic response
            print('-> '+ str(conn_list[raddr]), end='\r')

        # serialise the cache data to disk
        with open('info_cache', 'wb') as data_t:
            pickle.dump(info_list, data_t)        

        # produce a readable report on active connections list
        ReportWriter.write(conn_list, info_list, mr)
        print('report produced with '+ str(len(conn_list)) +' connections and '+ str(len(info_list)) +' cached entries')

        # quit if triggered
        if g_quit_flag or args.sp:
            break

        # length of sleep depending on CL flag
        if args.m:
            print('repeating the process in '+ str(args.m) +' minutes')
            time.sleep(args.m*60)
        else:
            time.sleep(g_refresh_interval)

# kb hook and entry point
def _quit():
    global g_quit_flag
    g_quit_flag = True
    print('quit signal invoked...')
keyboard.add_hotkey('ctrl+q', _quit)
if __name__ == "__main__":
    main()
