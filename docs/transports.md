## Transports
This table defines what transports are used with each platform to pull the data. The bottom line is that SSH is used with every platform except EOS. Why did we choose this model? It was easy to get REST API working with EOS, while SSH is the native transport for Linux-based devices. SSH just works with the other platforms and so we stuck with using SSH, while using EOS to flesh out our REST transport.

|         | Cumulus Linux | Arista EOS | Linux | Cisco NxOS | Cisco IOS, XE, XR | Juniper JunOS |
| :---------: | :---------------: | :------------: | :-------: | :------: | :-------: | :-------: |
| SSH | Yes | No | Yes | Yes | Yes | Yes |
| REST | No | Yes | No | No | No | No |
