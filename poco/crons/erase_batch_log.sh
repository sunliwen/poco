# delete the temp files on batch server later than x days
# this script should be invoked at 3:00 AM everyday

LOGPATH=/cube/service/batch/work_dir/vegaga
DAYS=7

find $LOGPATH -type d -mmin +$((60*24*$DAYS)) | xargs rm -rf
