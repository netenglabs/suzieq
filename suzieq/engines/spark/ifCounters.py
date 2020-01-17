def get_ifbw_df(
    datacenter: typing.List[str],
    hostname: typing.List[str],
    ifname: typing.List[str],
    columns: typing.List[str],
    start_time: str,
    end_time: str,
    cfg,
    schemas,
):
    """Return a DF for interface bandwidth for specified hosts/ifnames"""

    start = time.time()
    if isinstance(ifname, str) and ifname:
        ifname = [ifname]

    if isinstance(hostname, str) and hostname:
        hostname = [hostname]

    if isinstance(datacenter, str) and datacenter:
        datacenter = [datacenter]

    if ifname:
        ifname_str = "("
        for i, ele in enumerate(ifname):
            prefix = " or " if i else ""
            ifname_str += "{}ifname=='{}'".format(prefix, ele)

        ifname_str += ")"
    else:
        ifname_str = ""

    if hostname:
        hostname_str = "("
        for i, ele in enumerate(hostname):
            prefix = " or " if i else ""
            hostname_str += "{}hostname=='{}'".format(prefix, ele)
        hostname_str += ")"
    else:
        hostname_str = ""

    if datacenter:
        dc_str = "("
        for i, ele in enumerate(datacenter):
            prefix = " or " if i else ""
            dc_str += "{}datacenter=='{}'".format(prefix, ele)
        dc_str += ")"
    else:
        dc_str = ""

    wherestr = ""
    for wstr in [dc_str, hostname_str, ifname_str]:
        if wstr:
            if wherestr:
                wherestr += " and "
            else:
                wherestr += "where "

            wherestr += wstr

    qstr = (
        "select datacenter, hostname, ifname, {}, timestamp "
        "from ifCounters {} order by datacenter, hostname, ifname, "
        "timestamp".format(", ".join(columns), wherestr)
    )

    df = get_query_df(qstr, cfg, schemas, start_time, end_time, view="all")
    print("Fetch took {}s".format(time.time() - start))
    for col_name in columns:
        df["prevBytes(%s)" % (col_name)] = df.groupby(
            ["datacenter", "hostname", "ifname"]
        )[col_name].shift(1)
    df["prevTime"] = df.groupby(["datacenter", "hostname", "ifname"])[
        "timestamp"
    ].shift(1)

    idflist = []

    g = df.groupby(["datacenter", "hostname", "ifname"])
    for key in g:
        dele, hele, iele = key[0]
        dflist = []
        for col_name in columns:
            subdf = df.where(
                (df["datacenter"] == dele)
                & (df["hostname"] == hele)
                & (df["ifname"] == iele)
            )[
                [
                    "datacenter",
                    "hostname",
                    "ifname",
                    col_name,
                    "timestamp",
                    "prevTime",
                    "prevBytes(%s)" % col_name,
                ]
            ]
            subdf = subdf.dropna()
            subdf["rate(%s)" % col_name] = (
                subdf[col_name].sub(subdf["prevBytes(%s)" % (col_name)]) * 8
            ) / (subdf["timestamp"].sub(subdf["prevTime"]))
            subdf["timestamp"] = pd.to_datetime(subdf["timestamp"], unit="ms")
            dflist.append(
                subdf.drop(columns=[col_name, "prevBytes(%s)" % (col_name), "prevTime"])
            )

        if len(dflist) > 1:
            newdf = dflist[0]
            for i, subdf in enumerate(dflist[1:]):
                newdf = pd.merge(
                    newdf,
                    subdf[["rate(%s)" % (columns[i + 1]), "timestamp"]],
                    on="timestamp",
                    how="left",
                )
        else:
            newdf = dflist[0]

        idflist.append(newdf)

    if len(idflist) > 1:
        newdf = idflist[0]
        for i, subdf in enumerate(idflist[1:]):
            newdf = pd.concat([newdf, subdf])
    else:
        newdf = idflist[0]

    return newdf
