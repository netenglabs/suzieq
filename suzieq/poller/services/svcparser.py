import re
import ast


def _stepdown_rest(entry) -> list:
    '''move the elements one level down into the existing JSON hierarchy.

    if `entry` has the structure {'vrfs': {'routes'...} on invocation,
    it'll be {'routes'...} on exit. It makes no sense to move down them
    hierarchy when you have only a list.
    '''
    if isinstance(entry["rest"], dict):
        keylist = list(entry["rest"].keys())
        data = entry["rest"]
        entry = []
        for key in keylist:
            entry += [{"rest": data[key]}]
    else:
        entry = [entry]

    return entry


def cons_recs_from_json_template(tmplt_str, in_data):
    ''' Return an array of records given the template and input data.

    This uses an XPATH-like template string to create a list of records
    matching the template. It also normalizes the key fields so that we
    can create records with keys that are agnostic of the source.

    I could not use a ready-made library like jsonpath because of the
    difficulty in handling normalization and how jsonpath returns the
    result. For example, if I have 3 route records, one with 2 nexthop IPs,
    one with a single nexthop IP and one without a nexthop IP, jsonpath
    returns the data as a single flat list of nexthop IPs without a hint of
    figuring out which route the nexthops correspond to. We also support
    some amount of additional processing on the extracted fields such as
    the basic 4 arithmetic operations and specifying a default or
    substitute.
    '''
    result = []
    # Find prefix string
    try:
        ppos = re.search(r'/\[\s+', tmplt_str).start()
    except AttributeError:
        ppos = tmplt_str.index('[')

    # templates have a structure with a leading hierarchy traversal
    # followed by the fields for each record within that hierarchy.
    # One example is: vrfs/*:vrf/routes/*:prefix/[... where '[' marks
    # the start of the template to extract the values from the route
    # records (prefix) across all the VRFs(vrf). We break up this
    # processing into two parts, one before we reach  the inner record
    # (before '[') and the other after.
    #
    # Before we enter the inner records, we flatten the hierarchy by
    # creating as many records as necessary with the container values
    # filled into each record as a separate key. So with the above
    # template, we transform the route records to carry the vrf and the
    # prefix as fields of each record. Thus, when we have 2 VRFs and 10
    # routes in the first VRF and 6 routes in the second VRF, before
    # we're done with the processing of the prefix hierarchy, the result
    # has 16 records (10+6 routes) with the VRF and prefix values contained
    # in each record.
    #
    # We flatten because that is how pandas (and pyarrow) can process the
    # data best and queries can be made simple. The only nested structure
    # we allow is a list in the innermost fields. Thus, the list of nexthop
    # IP addresses associated with a route or the list of IP addresses
    # associated with an interface are allowed, but not a tuple consisting
    # of the nexthopIP and oif as a single entry.
    data = in_data
    nokeys = True
    try:
        pos = tmplt_str.index("/")
    except ValueError:
        ppos = 0                # completely flat JSON struct
    while ppos > 0:
        xstr = tmplt_str[0:pos]

        if ":" not in xstr:
            if not result:
                if xstr != '*':
                    if not data or not data.get(xstr, None):
                        # Some outputs contain just the main key with a null
                        # body such as ospfNbr from EOS: {'vrfs': {}}.
                        return result
                    result = [{"rest": data[xstr]}]
                else:
                    result = [{"rest": []}]
                    for key in data.keys():
                        result[0]["rest"].append(data[key])
            else:
                if xstr != "*":
                    # Handle xstr being a specific array index or dict key
                    if xstr.startswith('['):
                        xstr = ast.literal_eval(xstr)
                        result[0]["rest"] = eval("{}{}".format(
                            result[0]["rest"], xstr))
                    else:
                        if xstr not in result[0]["rest"]:
                            return result
                        for ele in result:
                            # EOS routes case: vrfs/*:vrf/routes/*:prefix
                            # Otherwise there's usually one element here
                            ele["rest"] = ele["rest"][xstr]
                else:
                    result = list(map(_stepdown_rest, result))
                    if len(result) == 1:
                        result = result[0]
                    else:
                        # Handle the output of the likes of EOS' BGP with
                        # starting string: 'vrfs/*/peerList/*/[
                        tmpres = result[0]
                        for entry in result[1:]:
                            tmpres[0]['rest'].extend(entry[0]['rest'])
                        result = tmpres

            tmplt_str = tmplt_str[pos + 1:]
            try:
                pos = tmplt_str.index("/")
            except ValueError:
                # its ppossible the JSON data is entirely flat
                ppos = 0
                continue
            ppos -= pos
            continue

        lval, rval = xstr.split(":")
        nokeys = False
        ks = [lval]
        tmpres = []
        if result:
            for ele in result:
                if lval == "*":
                    ks = list(ele["rest"].keys())

                intres = [{rval: x,
                           "rest": ele["rest"][x]}
                          for x in ks]

                for oldkey in ele.keys():
                    if oldkey == "rest":
                        continue
                    for newele in intres:
                        newele.update({oldkey: ele[oldkey]})
                tmpres += intres
            result = tmpres
        else:
            if lval == "*":
                ks = list(data.keys())

            result = [{rval: x,
                       "rest": data[x]} for x in ks]

        tmplt_str = tmplt_str[pos + 1:]
        pos = tmplt_str.index("/")
        ppos -= pos

    # Now for the rest of the fields
    # if we only have 'rest' as the key, break out into individual mbrs
    if nokeys:
        if not result:
            result = [{"rest": data}]
        elif len(result) == 1:
            tmpval = []
            for x in result[0]["rest"]:
                tmpval.append({"rest": x})
            result = tmpval

    # In some cases such as FRR's BGP, you need to eliminate elements which
    # have no useful 'rest' field, for example the elements with vrfId and
    # vrfName. If at this point, you have nn element in result with rest
    # that is not a list or a dict, remove it

    result = list(filter(lambda x: isinstance(x["rest"], list) or
                         isinstance(x["rest"], dict),
                         result))

    # The if handles cases of flat JSON data such as evpnVni
    if tmplt_str.startswith('/['):
        tmplt_str = tmplt_str[2:-1]
    else:
        tmplt_str = tmplt_str[1:][:-1]         # eliminate'[', ']'
    for selem in tmplt_str.split(","):
        # every element here MUST have the form lval:rval
        selem = selem.replace('"', '').strip()
        if not selem:
            # dealing with trailing "."
            continue

        lval, rval = selem.split(":")

        # Process default value processing of the form <key>?|<def_val> or
        # <key>?<expected_val>|<def_val>
        op = None
        if "?" in rval:
            rval, op = rval.split("?")
            exp_val, def_val = op.split("|")

            # Handle the case that the values are not strings
            if def_val.isdigit():
                def_val = int(def_val)
            elif def_val:
                # handle array indices
                try:
                    adef_val = ast.literal_eval(def_val)
                    def_val = adef_val
                except ValueError:
                    pass

        # Process for every element in result so far
        # Handles entries such as "vias/*/nexthopIps" and returns
        # a list of all nexthopIps.
        for x in result:
            if "/" in lval:
                subflds = lval.split("/")
                tmpval = x["rest"]
                value = None
                if "*" in subflds:
                    # Returning a list is the only supported option for now
                    value = []

                while subflds:
                    subfld = subflds.pop(0).strip()
                    if subfld == "*":
                        tmp = tmpval
                        for subele in tmp:
                            for ele in subflds:
                                if isinstance(tmp, list):
                                    subele = subele.get(ele, None)
                                else:
                                    subele = tmp[subele].get(ele, None)
                                if subele is None:
                                    break
                            if subele:
                                value.append(subele)
                        subflds = []
                    elif subfld.startswith('['):
                        # handle specific array index or dict key
                        # We don't handle a '*' in this position yet
                        assert(subfld != '[*]')
                        if tmpval:
                            tmpval = eval('tmpval{}'.format(subfld))
                    else:
                        tmpval = tmpval.get(subfld, None)
                    if not tmpval:
                        break

                if value is None:
                    value = tmpval
            else:
                value = x["rest"].get(lval.strip(), None)

            if op:
                if exp_val and value != exp_val:
                    value = def_val
                elif not exp_val and not value:
                    value = def_val

            # Handle any operation on string
            rval = rval.strip()
            rval1 = re.split(r"([+/*-])", rval)
            if len(rval1) > 1:
                iop = rval1[1]
                if value is not None:
                    if rval1[0] in x:
                        value = eval("{}{}{}".format(value, iop, x[rval1[0]]))
                    else:
                        value = eval("{}{}{}".format(value, iop, rval1[2]))
                try:
                    x.update({rval1[0]: value})
                except ValueError:
                    x.update({rval1[0]: value})
                continue

            if (isinstance(value, str) and value.startswith('"') and
                    value.endswith('"')):
                # Strip leading and trailing quotes from string
                x.update({rval: value[1:-1]})
            else:
                x.update({rval: value})

    list(map(lambda x: x.pop("rest", None), result))

    return result
