import re
import ast
import logging
import operator as op


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


def parse_subtree(subflds, tmpval, maybe_list, defval):

    value = []
    useval = False

    for i, subfld in enumerate(subflds):
        subfld = subfld.strip()
        if ':_sqstore' in subfld:
            storekey = True
            subfld = '*'
        else:
            storekey = False
        if subfld == "*":
            tmp = tmpval
            for subele in tmp:
                if storekey:
                    storeval = subele
                for ele in subflds[i+1:]:
                    if isinstance(tmp, list):
                        subele = subele.get(ele, None)
                    else:
                        subele = tmp[subele].get(ele, None)
                    if subele is None:
                        tmpval = None
                        break
                if subele:
                    if storekey:
                        value.append(storeval)
                    else:
                        value.append(subele)
                    useval = True
            break
        elif subfld.startswith('['):
            # handle specific array index or dict key
            # This additional handling of * is because of JUNOS
            # interface address which is many levels deep and mixes
            # IPv4/v6 address in a way that we can't entirely fix
            # Post processing cleanup has to handle that part
            if subfld.endswith('?'):
                # This was added thanks to NXOS which provides
                # nexthops as a list if ECMP, else a dictionary
                if type(tmpval) != list:
                    continue
                subfld = subfld[:-1]  # lose the final "?" char
            if subfld == '[*]':
                for item in tmpval:
                    newval = parse_subtree(subflds[i+1:], item, maybe_list,
                                           defval)
                    if newval is not None:
                        if isinstance(newval, list):
                            value += newval
                        else:
                            value.append(newval)
                useval = True
                break
            elif tmpval:
                tmpval = tmpval[eval_expr(subfld)]
        else:
            tmpval = tmpval.get(subfld, None)

        if not tmpval:
            break

    if useval:
        if value:
            return value
        else:
            return defval
    else:
        return tmpval


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
                if xstr != '*' and xstr != '*?':
                    if not data or not data.get(xstr, None):
                        # Some outputs contain just the main key with a null
                        # body such as ospfNbr from EOS: {'vrfs': {}}.
                        logging.info(
                            f"Unnatural return from svcparser. xstr is {xstr}. \
                            Result is {result}")
                        return cleanup_and_return(result)
                    result = [{"rest": data[xstr]}]
                else:
                    if isinstance(data, dict):
                        result = [{"rest": []}]
                        for key in data.keys():
                            result[0]["rest"].append(data[key])
                    else:
                        result = [{"rest": data}]
            else:
                if xstr != "*" and xstr != '*?':
                    # Handle xstr being a specific array index or dict key
                    if xstr.startswith('['):
                        if len(result[0]['rest']):
                            result[0]["rest"] = result[0]["rest"][eval_expr(
                                xstr)]
                        else:
                            # Handling the JUNOS EVPN pfx DB entry
                            logging.info(
                                f'Unnatural return from svcparser. '
                                f'xstr is {xstr}. Result is {result}')
                            return []

                    else:
                        tmpval = []
                        for ele in result:
                            # EOS routes case: vrfs/*:vrf/routes/*:prefix
                            # Otherwise there's usually one element here
                            if isinstance(ele["rest"], list):
                                for subidx, subele in enumerate(ele["rest"]):
                                    if xstr in subele:
                                        if nokeys:
                                            tmpval.append(
                                                {"rest": subele[xstr]})
                                        else:
                                            ele['rest'][subidx] = subele[xstr]
                                if not nokeys:
                                    if len(ele['rest']) == 1:
                                        ele['rest'] = ele['rest'][0]

                                    tmpval.append(ele)
                            else:
                                if xstr in ele['rest']:
                                    ele["rest"] = ele["rest"][xstr]
                        if tmpval:
                            result = tmpval
                else:
                    if (xstr == '*?'):
                        # Massaging the format to handle cases like NXOS that
                        # provide dict when there's a single element and a list
                        # if there's more than one element
                        tmpres = []
                        for item in result:
                            if not isinstance(item, list):
                                if not isinstance(item['rest'], list):
                                    item['rest'] = [item['rest']]
                                tmpres.append([item])
                        result = tmpres
                    else:
                        result = list(map(_stepdown_rest, result))
                    if len(result) == 1:
                        result = result[0]
                    else:
                        tmpres = result[0]
                        if tmpres[0].keys() != set(['rest']):
                            # Handle output like EOS OSPF output with the
                            # starting string:
                            # vrfs/*:vrf/instList/*:instance/ospfNeighborEntries/*/[
                            # Move the keys into each element of the lists
                            # we need to pop out these keys at the very end
                            for entry in result:
                                elekeys = entry[0].keys() - set(['rest'])
                                if not elekeys:
                                    # this happens when NXOS routes returns
                                    # half-baked data when there are no routes
                                    # in a VRF.
                                    continue
                                for rstentry in entry[0]['rest']:
                                    rstentry['sq-addnl-keys'] = []
                                    for key in elekeys:
                                        rstentry['sq-addnl-keys'].append({
                                            key: entry[0][key]})
                                for key in elekeys:
                                    del entry[0][key]
                                # We should only have 'rest' entries now
                            nokeys = True  # We've moved all the external keys in

                        # Handle the output of the likes of EOS' BGP with
                        # starting string: 'vrfs/*/peerList/*/[ by
                        # merging the rest lists
                        for entry in result[1:]:
                            tmpres[0]['rest'].extend(entry[0]['rest'])
                        result = tmpres

            tmplt_str = tmplt_str[pos + 1:]
            if re.match(r'^\[\s+"', tmplt_str):
                ppos = 0
                continue
            try:
                pos = tmplt_str.index("/")
            except ValueError:
                # its ppossible the JSON data is entirely flat
                ppos = 0
                continue
            ppos -= pos
            continue

        # handle one level of nesting to deal with Junos route JSON, NXOS route
        # and many others that have an interesting field in parallel with
        # the rest of the useful data
        *lval, rval = xstr.split(":")
        if "|" in rval:
            rval, nxtfld = rval.split('|')
        else:
            nxtfld = None
        nokeys = False
        ks = [lval[0]]
        tmpres = []
        intres = []
        if result:
            for ele in result:
                if lval[0] == "*":
                    if isinstance(ele['rest'], dict):
                        if nxtfld:
                            intres = [{rval: ele['rest'].get(lval[1], ''),
                                       "rest": ele['rest'].get(nxtfld, [])}]
                        else:
                            ks = list(ele["rest"].keys())

                            intres = [{rval: x,
                                       "rest": ele["rest"][x]}
                                      for x in ks]
                    else:
                        if nxtfld:
                            intres = [{rval: x.get(lval[1], ''),
                                       "rest": x.get(nxtfld, [])}
                                      for x in ele["rest"]]
                        else:
                            intres = [{rval: x.get(lval[1], ''), "rest": x}
                                      for x in ele["rest"]]

                for oldkey in ele.keys():
                    if oldkey == "rest":
                        continue
                    for newele in intres:
                        newele.update({oldkey: ele[oldkey]})
                tmpres += intres
            result = tmpres
        else:
            if lval == ["*"]:
                ks = list(data.keys())

            result = [{rval: x,
                       "rest": data[x]} for x in ks]

        tmplt_str = tmplt_str[pos + 1:]
        try:
            # handle EOS' ospfIf output
            pos = tmplt_str.index("/")
        except ValueError:
            pos = ppos
        ppos -= pos

    # Now for the rest of the fields
    # if we only have 'rest' as the key, break out into individual mbrs
    if nokeys:
        if not result:
            result = [{"rest": data}]
        elif len(result) == 1:
            if isinstance(result[0], list):
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

    # At this point, we're expecting result to contain a list where each
    # entry contains the "rest' key with the fields from which further data
    # is to be extracted, and a series of keys which represent what has already
    # been extracted from the header string. If the format of result isn't
    # this, fix it
    if len(result) == 1 and isinstance(result[0]['rest'], list):
        tmpres = []
        entry = result[0]
        elekeys = entry.keys() - set(['rest'])
        for elem in entry['rest']:
            newentry = {}
            [newentry.update({x: entry[x]}) for x in elekeys]
            newentry['rest'] = elem
            tmpres.append(newentry)
        result = tmpres

    # The if handles cases of flat JSON data such as evpnVni
    if tmplt_str.startswith('/['):
        tmplt_str = tmplt_str[2:-1]
    else:
        tmplt_str = tmplt_str[1:][:-1]         # eliminate'[', ']'
    for selem in tmplt_str.split(","):
        per_entry_defval = False
        def_val = None
        # every element here MUST have the form lval:rval
        selem = selem.replace('"', '').strip()
        if not selem:
            # dealing with trailing "."
            continue

        try:
            lval, rval = selem.split(": ")
        except ValueError:
            logging.error(f"Unable to parse JSON field entry {selem}")
            continue

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
                if result and def_val not in result[0]:
                    # handle array indices, such as [] for default
                    # If the field to be init is a prev val, then handle this
                    # in the loop for x below as its different for each entry
                    # an example of such an entry is:
                    # "advertisedAndReceived: v4Enabled?|v4Enabled"
                    # which means if advertisedAndReceived is not found in this
                    # iteration, retain the previous value. This is useful when
                    # handling minor changes in JSON output such as one version
                    # with a key 'Advertised And Received' changing to
                    # 'advertisedAndReceived' in the next version of output
                    try:
                        adef_val = ast.literal_eval(def_val)
                        def_val = adef_val
                    except ValueError:
                        pass
                else:
                    per_entry_defval = True

        # Process for every element in result so far
        # Handles entries such as "vias/*/nexthopIps" and returns
        # a list of all nexthopIps.
        for x in result:

            loopdef_val = def_val
            if per_entry_defval and def_val is not None:
                if def_val in x:
                    loopdef_val = x[def_val]
                else:
                    loopdef_val = ''  # this shouldn't happen

            if "/" in lval:
                subflds = lval.split("/")
                tmpval = x["rest"]
                value = None
                if any(x in subflds for x in ["*", "*?", "[*]?", "[*]",
                                              '*:_sqstore']):
                    # Returning a list is the only supported option for now
                    value = []
                    maybe_list = True
                else:
                    maybe_list = False

                value = parse_subtree(
                    subflds, tmpval, maybe_list, loopdef_val)
                subflds = []
            else:
                value = x["rest"].get(lval.strip(), None)

            if op:
                if exp_val and value != exp_val:
                    value = loopdef_val
                elif not exp_val:
                    if (isinstance(value, list) and not
                            any(x or (x == loopdef_val) for x in value)):
                        if not isinstance(loopdef_val, list) and maybe_list:
                            if loopdef_val == '':
                                value = []
                            else:
                                value = [loopdef_val]
                        else:
                            value = loopdef_val
                    elif not value:
                        value = loopdef_val

            # Handle any operation on string
            rval = rval.strip()
            rval1 = re.split(r"([+/*-])", rval)
            if len(rval1) > 1:
                iop = rval1[1]
                if value is not None:
                    if rval1[0] in x:
                        value = eval_expr(f'{value}{iop}{x[rval1[0]]}')
                    else:
                        value = eval_expr(f'{value}{iop}{rval1[2]}')
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

    return cleanup_and_return(result)


def cleanup_and_return(result):
    for entry in result:
        # To handle entries like EOS' ospfNbr, we had saved the multiple keys
        # extracted from the initial part of the JSON string and saved it in
        # sq-addnl-keys. Now pop them out into the appropriate spot before
        # eliminating the 'rest' field which contains the unused fields
        rest = entry.pop('rest', {})
        if 'sq-addnl-keys' in rest:
            for elem in rest['sq-addnl-keys']:
                entry.update(elem)

    return result


def eval_expr(expr):
    """Evaluate numerical expression without eval or other packages"""
    return num_eval(ast.parse(expr, mode='eval').body)


def num_eval(node):
    # supported arithmetic operators
    operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
                 ast.Div: op.truediv, ast.Pow: op.pow}

    if isinstance(node, ast.Num):  # <number>
        return node.n
    elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
        return operators[type(node.op)](num_eval(node.left),
                                        num_eval(node.right))
    elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
        return operators[type(node.op)](num_eval(node.operand))
    elif isinstance(node, ast.List):
        return node.col_offset
    else:
        raise TypeError(node)
