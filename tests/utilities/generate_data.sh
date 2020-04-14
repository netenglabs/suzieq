#!/bin/bash
# it gathers data with the suzieq poller
# so you need to be in a python environment that can run suzieq

suzieq_dir=/tmp/pycharm_project_304/suzieq/suzieq

run_sqpoller () {
    topology="$1"
    name="$2"
    echo ${name}
    ansible_dir=~/cloud-native-data-center-networking/topologies/${topology}/.vagrant
    ansible_file=${ansible_dir}/provisioners/ansible/inventory/vagrant_ansible_inventory
    sudo chown -R jpiet ${ansible_dir}
    echo "SUZIEQ"
    python3 ${suzieq_dir}/poller/sq-poller -i ${ansible_file} -n ${name}  >> ${verbose_log} 2>&1 &
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
        return RESULT_sq
    fi
    table=$(python3 ${suzieq_dir}/cli/suzieq-cli device unique --columns=namespace --namespace=${name})
    echo ${table}
    RESULT_sq=$?
    if (( ${RESULT_sq} > 0 )) ; then
        return RESULT_sq
    fi
    data=$(echo ${table} | grep 14)
    echo "DATA " ${data}
    if [ -z "$data" ] ; then
       echo "Missing hosts " ${table}
       exit 1
    fi

    return 0
}

run_scenario () {
    topology="$1"
    proto="$2"
    scenario="$3"
    name="$4"
    echo "SCENARIO $topology $proto $scenario" >> ${log} 2>&1
    pwd
    time sudo ansible-playbook -b -e "scenario=$scenario" deploy.yml >> ${verbose_log} 2>&1
    echo "DEPLOY RESULTS $?" >> ${log} 2>&1
    sleep 15 #on fast machines, not everything is all the way up without sleep
    sudo ansible-playbook ping.yml >> ${verbose_log} 2>&1
    RESULT_sc=$?
    echo "PING RESULTS $RESULT_sc" >> ${log} 2>&1
    #return RESULT_sq
}

run_protos () {
    topology="$1"
    proto="$2"

    scenario="$3"
    name="$4"
    tries=2

    echo ${proto} >> ${log} 2>&1
    cd ${proto}
    RESULT_sc=99
    while (( ${RESULT_sc} > 0 )) && (( ${tries} > 0 )); do
        vagrant_down
        vagrant_up
        echo ${RESULT_sc} ${tries}
        run_scenario ${topology} ${proto} ${scenario} ${name}
        tries=$(expr ${tries} -1)
        echo "RESULT: " ${RESULT_sc} ${tries}
    done
    if (( ${RESULT_sc} > 0 )) ; then
        echo "FAILED vagrant or ansible" >> ${log}
        vagrant_down
        exit 1
    fi
    run_sqpoller ${topology} ${name} >> ${log} 2>&1
    if (( ${RESULT_sq} > 0 )) ; then
        echo "FAILED sqpoller" >> ${log}
        vagrant_down
        exit 1
    fi
    vagrant_down
    cd ..
}

vagrant_down () {
    sudo vagrant destroy -f >> ${verbose_log} 2>&1
    echo "VAGRANT DESTROY RESULTS $?" >> ${log} 2>&1

}

vagrant_up () {
    echo 'foo' >> ${verbose_log}
    time sudo vagrant up >> ${verbose_log} 2>&1
    echo "VAGRANT UP %?" >> ${log} 2>&1
    sudo vagrant status >> ${log} 2>&1
}

log=`pwd`/log
verbose_log=${log}.verbose
echo ${log}
echo ${verbose_log}
date > ${log}
date > ${verbose_log}

rm -rf ~/parquet-out
topology='dual-attach'
cd ${topology}
run_protos ${topology} evpn ospf-ibgp ospf-ibgp
run_protos ${topology} evpn centralized dual-evpn
cd ..
topology='single-attach'
cd ${topology}
run_protos ${topology} ospf numbered ospf-single
cd ..
mv ~/parquet-out ~/parquet-out-multidc

topology='dual-attach'
cd ${topology}
run_protos ${topology} bgp numbered dual-bgp
mv ~/parquet-out ~/parquet-out-basic_dual_bgp
date >> ${log}
