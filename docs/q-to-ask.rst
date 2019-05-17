***************************
Questions SuzieQ can answer
***************************

Device Questions
****************
    * What is the device model?
    * What is the operating threshold for temp across devices?
    * What versions of software am I running?
    * What version of a specific package am I running?
    * What are the avg device uptimes? For leaves? For spines? For servers?
    * What is the avg CPU load on leaves? On spines?
    * What is the max CPU load on leaves? On spines?
    * Is there a pattern to when the CPU load is maximum? Time of Day?
    * What is the avg mem utilization on leaves? On spines?
    * What is the max mem used on leaves? On spines?
    * What devices have any downed links?

Link Questions
****************
    * What MTUs are my server ports configured for?
    * What MTUs are my ISL links configured for?
    * What is the Path MTU between a given src & dst?
    * Are there any MTU mismatches? [X]
    * What is the polarization of my uplinks on a specific switch?
    * What is the polarization on my uplinks across all leaves?
    * Which link has the most flaps? Any pattern to these flaps?
    * What is the list of down links?
    * When was the last time a specific link(s) was down?
    * admin down vs cable down

Services Questions
******************
    * What services are running on any given node?
    * What nodes are running a particular service?
    * Last uptime of any given service on a node?
    * Any nodes with enabled service but inactive?
    * Any nodes with active service but not enabled?
    * Top-n flaky services

OSPF Questions
**************
    * Are all the router-ids unique? [X]
    * Are all the router-ids used with loopback?
    * Who's announcing the default route?
    * Are my OSPF links configured as p2p? (affects convergence) 
    * What is the OSPF neighbor uptime avg? The nbr with the least uptime?
    * What was the cause of the last SPF? [Not in log anymore]
    * What is the Current state of all nbrs? [X]
    * When was the last time a nbr was in a bad state?

Server Questions
****************
    * Who's the most chatty server? Top 10?
    * On my server which is the most chatty process? Top 10?
    * What are the avg mem utilization across my servers?

Container Questions
*******************
    * Where is a given container running?
    * What are the avg number of containers running on my servers?
    * What is the docker version?
    * What network types are used with containers?


Kubernetes Questions
********************
    * How many clusters?
    * Who are the K8s masters?
    * Any overlap in cluster membership?

Systemic Questions
******************
    * Show all events within a given time window
    * Cause & effect
    * Top-n of various stuff

Platina-specific
****************

    * K8s and underlay infra addr space clash
