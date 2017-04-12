#!/bin/bash
# requires inotify-tools and libnotify-bin
status=12

# http://stackoverflow.com/a/1638397
script=$(readlink -f "$0")
script_folder=$(dirname "$SCRIPT")
albion_folder=$(realpath $script_folder/..)

if [ -f "$albion_folder/metadata.txt" ]; then
	read -p "Found folder: $albion_folder. OK? (y/N) " -n1 ans
	if [ "$ans" != "y" ]; then
		exit 0
	fi
	echo ''
else
	echo "Failed to find albion folder. Aborting"
	exit 1
fi

build() {
	echo 'Build albion'
	find $albion_folder -name "*.pyc" -exec rm '{}' \;
	PYTHONPATH=$albion_folder python -m albion.package -i
	pytest

	new_status=$?
	if [ $new_status -eq 0 ]
	then
		echo 'OK'

		if [ $new_status != $status ]
		then
			notify-send -i emblem-default 'albion build status: OK'
		fi
	else
		if [ $new_status != $status ]
		then
			notify-send -i emblem-important 'albion build status: FAILED'
		fi
		echo 'Failed'
	fi
	status=$new_status
}

build
while inotifywait -q -q -r -e close_write $albion_folder @.git; do
	build
done
