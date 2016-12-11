# delete the temp files on batch server later than x days
# this script should be invoked at 3:00 AM everyday

# the logpath should be ``work_dir`` variable in services/batch/local_settings.py, plus SITE_ID
# You should set the correct value depends on your deploy
LOGPATH=/cube/data/poco/batch/work_dir/haoyaoshi
DAYS=7

find $LOGPATH -type d -mmin +$((60*24*$DAYS)) | xargs rm -rf
