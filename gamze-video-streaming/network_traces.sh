#!/bin/sh

#Traffic shaper TC:
#Read a trace .txt file in the form of:

#Time_1 Bw_1
#Time_2 Bw_2
#Time_3 Bw_3

#Time: float, interpreted as seconds
#Bw: float, interpreted as mbit

#Shape the bw according to the trace file. When the file ends, it starts again.
#PARAMETERS:
#1) Trace file path
#2) Dev interface to manipulate (retieve the name with "ifconfig" command)
#3) Output text file name -> logs the time stamp/bandwidth. Useful for plots (the experiment could run into several loops)

# Terminate -> CTRL + C 



# Name of the traffic control command.
TC=/sbin/tc
MBS="mbit"
M="mbit"


start() {
	sudo  modprobe ifb
	sudo  ip link set dev ifb0 up
	sudo $TC qdisc add dev $IF ingress
	sudo $TC filter add dev $IF parent ffff: protocol ip u32 match u32 0 0 flowid 1:1 action mirred egress redirect dev ifb0
	sudo $TC qdisc add dev ifb0 root tbf rate $RATE$MBS latency 50ms burst 1540
}

stop() {
    sudo $TC qdisc del dev $IF ingress
    sudo $TC qdisc del dev ifb0 root
    exit
}

modify(){

	sudo $TC qdisc change dev ifb0 root tbf rate $RATE$MBS latency 50ms burst 1540


}


if [ "$#" -le 2 ]; then
	echo "USAGE: <FILENAME> <DEV_INTERFACE> <OUT>"
	exit
fi

trap stop 2


filename="$1"
IF="$2"
OUT="$3"
RATE="1"
echo "Starting " $filename
echo $IF # stores the device name (usually eth0)

start
offset=0

touch "$OUT"
while true
do
	time_now=0
	while read -r line
	do
		name="$line"
		#set -f; IFS=' '
		#set -f; IFS=$'\t' # set splitting to tab
		set -- $line
		time=$1; bw=$2
		#set +f; unset IFS

		time_to_sleep=$( echo "($time-$time_now)" | bc -l )
		sleep $time_to_sleep
		time_now=$time
		RATE=$bw
		timestamp=$( echo "($time+$offset)" | bc -l )
		#echo "$timestamp $RATE" >> $OUT
		#echo "$timestamp $RATE"
		modify
	
	done < "$filename"
	offset=$( echo "($offset+$time_now)" | bc -l )
done

echo "Stopping"
stop
