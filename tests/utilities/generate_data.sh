#!/bin/bash
# it gathers data with the suzieq poller
# so you need to be in a python environment that can run suzieq
# this is run in the cloud-native-data-center-networking/topologies directory

suzieq_dir=/home/jpiet/suzieq-dev/suzieq
parquet_dir=/home/${USER}/parquet-out
archive_dir=/home/${USER}/parquet_files

run_sqpoller () {
    topology="$1"
    name="$2"
    echo ${name}
    ansible_dir=~/cloud-native-data-center-networking/topologies/${topology}/.vagrant
    ansible_file=${ansible_dir}/provisioners/ansible/inventory/vagrant_ansible_inventory
    sudo chown -R ${USER} ${ansible_dir}
    echo "SUZIEQ"
    python3 ${suzieq_dir}/poller/sq-poller -a ${ansible_file} -n ${name} &
    RESULT_sq=$?
    if (( ${RESULT_sq} > 0 )) ; then
        return RESULT_sq
    fi
    sleep 180
    pkill -f sq-poller
    ps auxwww | grep poller
    echo "SUZIEQ poller done"
    sleep 15
    python3 ${suzieq_dir}/cli/suzieq-cli table show
    RESULT_sq=$?
    if (( ${RESULT_sq} > 0 )) ; then
        echo "table show FAILED ${RESULT_sq}"
        return 1
    fi
    table=$(python3 ${suzieq_dir}/cli/suzieq-cli device unique --columns=namespace --namespace=${name})
    echo ${table}
    RESULT_sq=$?
    if (( ${RESULT_sq} > 0 )) ; then
        return ${RESULT_sq}
    fi
    data=$(echo ${table} | grep 14)
    echo "DATA " ${data}
    if [[ -z "$data" ]] ; then
       echo "FAILED: Missing hosts " ${table}
       return ${data}
    fi
    python3 ${suzieq_dir}/cli/suzieq-cli interface assert --namespace=${name}
    echo "SUZIEQ interface assert RESULTS: $?"
    python3 ${suzieq_dir}/cli/suzieq-cli bgp assert --namespace=${name}
    echo "SUZIEQ bgp assert RESULTS: $?"
    python3 ${suzieq_dir}/cli/suzieq-cli ospf assert --namespace=${name}
    echo "SUZIEQ ospf assert RESULTS: $?"
    python3 ${suzieq_dir}/cli/suzieq-cli evpnVni assert --namespace=${name}
    echo "SUZIEQ evpnVni assert RESULTS: $?"
    return 0
}

run_scenario () {
    topology="$1"
    proto="$2"
    scenario="$3"
    name="$4"
    echo "SCENARIO ${topology} ${proto} ${scenario} ${name}"
    pwd
    date
    time sudo ansible-playbook -b -e "scenario=$scenario" deploy.yml
    echo "DEPLOY RESULTS $?"
    sleep 30 #on fast machines, not everything is all the way up without sleep
    sudo ansible-playbook ping.yml
    RESULT_sc=$?
    echo "PING RESULTS $RESULT_sc"
}

run_protos () {
    topology="$1"
    proto="$2"

    scenario="$3"
    name="$4"
    tries=2

    cd ${proto}
    RESULT_sc=99
    while (( ${RESULT_sc} > 0 )) && (( ${tries} > 0 )); do
        vagrant_up
        run_scenario ${topology} ${proto} ${scenario} ${name}
        tries=$(expr ${tries} - 1)
        echo "tries ${tries}"
        if (( ${RESULT_sc} > 0 )) ; then
            vagrant_down
        fi
    done
    if (( ${RESULT_sc} > 0 )) ; then
        echo "FAILED vagrant or ansible for ${topology} ${proto} ${scenario}"
    fi
    run_sqpoller ${topology} ${name}
    if (( ${RESULT_sq} > 0 )) ; then
        echo "FAILED sqpoller"
        vagrant_down
        cd ..
        return 1
    fi
    vagrant_down
    cd ..
}

vagrant_down () {
    sudo vagrant destroy -f
    echo "VAGRANT DESTROY RESULTS $?"
}

vagrant_up () {
    time sudo vagrant up
    echo "VAGRANT UP RESULTS $?"
    sudo vagrant status
}

del_parquet_dir () {
    rm -rf ${parquet_dir}
    if (( ${?} > 0 )) ; then
       echo "rm of ${parquet_dir} FAILED"
       exit 1
    fi
}

# this produces the data that we need in our test_sqcmds
create_test_data () {
    del_parquet_dir
    topology='dual-attach'

    cd ${topology}
    run_protos ${topology} evpn ospf-ibgp ospf-ibgp
    run_protos ${topology} evpn centralized dual-evpn
    cd ..
    topology='single-attach'
    cd ${topology}
    run_protos ${topology} ospf numbered ospf-single
    cd ..
    mv ${parquet_dir} ${parquet_dir}-multidc

    topology='dual-attach'

    cd ${topology}
    run_protos ${topology} bgp numbered dual-bgp
    mv ${parquet_dir} ${parquet_dir}-basic_dual_bgp
    cd ..
}

check_all_cndcn () {
   del_parquet_dir
   mkdir ${archive_dir}
   for topo in single-attach dual-attach
   do
       cd ${topo}
       vagrant_down # just to be sure
       for scenario in centralized distributed ospf-ibgp
       do
          name=${topo}_evpn_${scenario}
          run_protos ${topo} evpn ${scenario} ${name}
          tar czf ${archive_dir}/parquet_out_${name}.tgz ${parquet_dir}
          del_parquet_dir
       done
       for scenario in numbered unnumbered docker
       do
          for proto in bgp ospf
          do
              name=${topo}_${proto}_${scenario}
              run_protos ${topo} ${proto} ${scenario} ${name}
              tar czvf ${archive_dir}/parquet_out_${name}.tgz ${parquet_dir}
              del_parquet_dir
          done
       done
       cd ..
   done
}

check_log () {
   # grep through log to understand if things worked as expected
   egrep "SCENARIO|UTC|DATA|RESULT|FAILED|tries|FINISHED|tries|cd " ${log} | egrep -v "fatal|DESTROY"
}

clean_up () {
    date >> ${log}
    check_log
    mv ${log} ${archive_dir}
}

log=`pwd`/log
echo ${log}
date > ${log}
create_test_data >> ${log} 2>&1
echo "FINISHED test data" >> ${log}
check_all_cndcn >> ${log} 2>&1
echo "FINISHED" >> ${log}
clean_up
