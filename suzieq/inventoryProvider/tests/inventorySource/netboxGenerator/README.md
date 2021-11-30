# netboxGenerator directory
This directory contains both the NetboxGenerator class and the netbox REST server. This is done because both elements are hardly interconnected and the former cannot work without the latter.

**In the next steps I think there will be a run function inside the NetboxGenerator that will call the REST server, but for now they are threated like 2 separate things**

## netbox_rest_server.py
The goal of this file is to create a REST server which works exactly like a netbox one.

**At the time when this documentation was written the server will start on a fixed port, in the near future all its internals will be defined via a configuration file**

API paths supported:
- `GET: api/dcim/devices?tag={tag}&offset={offset}&limit={limit}`: returns the list of devices with the tag `tag`. Fields `offset` and `limit` are used when all the data cannot be fitted in a single request. 

    The default limit is 50 devices.
    The header must be contain `{"authorization": "Token this-is-an-example-token"}` and the token is validated before performing the request.
- `POST: api/users/tokens/provision`: returns a token if the credential sent with the request are valid.

    The request body must be similar to `{"username":"admin","password":"password"}`
- `POST: kill`: since there is no way to stop the server without killing the process, this path to exactly this thing. 

    **This path opened some controversies with my collegues. I'll keep it for now, we'll discuss about it in the future**

The APIs data is stored inside directories which has the same path as the API itself. In this way it's easy to add new APIs.

All the errors are stored inside the `./errors` directory and their name must follow the `<error_code>.<error_name>` format.
If no errors are found, it will launch a generic `500: Internal server error`

## NetboxGenerator
The NetboxGenerator class will generate both the devices and the tokens and store them in the correct directories.

The generation is pretty straight forward and I think there is no need to more explaination rather than the code itself.

What could be trickier to understand is the configuration file.
Its configuration is stored inside the `data` key in the `data_generator` config file.
Below there is the content of a generic netbox config.
```yaml
inventorySource:
    - name: netbox1
      type: netboxGenerator
      data:
        devices:                                    # contains the informations for all devices
          out_path: "api/dcim/devices"              # output path for devices
          out_format: "json"                        # output format (only json is supported)
          count: 10                                 # number of devices
          name: net1Device                          # root_name for devices. All devices will
                                                    # have a name starting with "net1Device"
          
          site_count: 2                             # number of different netbox sites
          ip:                                       # ip informations
            prob:                                   # probability field. The user can define
              "4": 0.1                              # for each ip version which is the
              "6": 0.9                              # probability that the device will have an
                                                    # ip or not
          tag:                                      # tag informations
            value: suzieq                           # tag value
            prob: 0.5                               # probability that the device has a tag
        tokens:                                     # contains the informations for all tokens
          list:                                     # list of tokens to generate
            - "0123456789123456789"
            - "akjasdpksdjcnaspkdjnfa"
          out_path: "api/users/tokens/provision"    # output path for tokens
          out_format: "json"                        # output format
```