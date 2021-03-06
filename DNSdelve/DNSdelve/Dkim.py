#!/usr/bin/python

""" DNSdelve module to detect DKIM use by checking the existence of
the _domainkey subdomain. We cannot get the TXT records since they
have a label which depends on the selectors (and there is no standard
way to get the list of selectors).

Quite broken at this time, better not to use it.
"""

# Standard modules
import Queue
import random
import getopt
import sys
import time
import re

# www.dnspython.org
import dns.resolver

# Local
import BaseResult
import BasePlugin
import Utils
import DNSwildcards

# Default settings 
database = "dkim"
num_writing_tasks = 10
write_delay = 2 # seconds
# TODO: the timeout of queries?

# Global
writers = []

def module_usage(msg=None):
    print >>sys.stderr, "Usage of this Dkim module: [-b database_name] [-r resolvers_addresses] [-n N] "
    if msg is not None:
        print >>sys.stderr, msg

class DkimResult(BaseResult.Result):
    
    def __init__(self):
        self.dkim = None
        BaseResult.Result.__init__(self)

    def __str__(self):
        return "DKIM: %s" % (self.dkim)

    def store(self, uuid):
        if self.dkim is not None:
            has_dkim = True
        else:
            has_dkim = False
        self.writer.channel.put(["tests", {"uuid": str(uuid), "domain":self.domain,
                                 "broken":self.zone_broken,
                                 "has_dkim": has_dkim}])
        
class Plugin(BasePlugin.Plugin):

    def query(self, zone, nameservers):
        global writers
        zone_broken = False
        dkim_result = None
        # Many domains have wildcards and therefore RR types like
        # A or ANY will always match. That's why we test wildcards.
        checker = DNSwildcards.Wildcards()
        wildcard_addresses = None
        # TODO: use the DNSdelve resolver, not the default resolver?
        try:
            wildcard_addresses = checker.has_wildcard (zone)
        except dns.resolver.Timeout:
            zone_broken = True
        if wildcard_addresses is not None:
            # We cannot say anything :-(
            dkim_result = None
        elif zone_broken:
            dkim_result = None
        else:
            try:
                dkim_result = myresolver.query ("_domainkey.%s" % zone, 'TXT')
                dkim_result = True
            except (dns.resolver.NXDOMAIN):
                dkim_result = False
            except dns.resolver.NoAnswer:
                # OK, the DKIM subdomain exists. It may be empty but we have no way to know it.
                dkim_result = True
            except (dns.resolver.NoNameservers, dns.resolver.Timeout):
                # No second chance: the zone is broken, we never try again
                dkim_result = None
                zone_broken = True
        fullresult = DkimResult()
        fullresult.zone_broken = zone_broken
        fullresult.dkim = dkim_result
        fullresult.domain = zone
        fullresult.writer = random.choice(writers)
        return fullresult

def config(args):
    global database, num_writing_tasks, resolvers
    resolvers = None
    try:
        optlist, args = getopt.getopt (args, "hn:b:r:",
                                       ["help", "num_tasks=", "database=", 
                                        "resolvers="])
        for option, value in optlist:
            if option == "--help" or option == "-h":
                module_usage()
                sys.exit(0)
            elif option == "--num_tasks" or option == "-n":
                num_writing_tasks = int(value)
            elif option == "--resolvers" or option == "-r":
                resolvers = value.split(',')
            elif option == "--database" or option == "-b":
                database = value
            else:
                # Should never occur, it is trapped by getopt
                module_usage("Internal error: unhandled option %s" % option)
                sys.exit(1)
    except getopt.error, reason:
        module_usage(reason)
        sys.exit(1)
    if len(args) != 0:
        module_usage()
        sys.exit(1)

def start(uuid, all_domains):
    global database, writers, myresolver, resolvers, num_writing_tasks
    myresolver = Utils.make_resolver(resolvers)
    Utils.write_domains(database, uuid, all_domains)
    writers = []
    for writer in range(1, num_writing_tasks+1):
        channel = Queue.Queue()
        writers.append(Utils.DatabaseWriter(writer, database, channel))
        writers[writer-1].start()

def final():
    global writers, write_delay
    time.sleep(write_delay) # Let the queries put the final data in the queues
    for writer in range(1, num_writing_tasks+1):
        writers[writer-1].channel.put([None, None])
    for writer in range(1, num_writing_tasks+1):
        writers[writer-1].join()

if __name__ == '__main__':
    raise Exception("Not yet usable as a main program, sorry")

