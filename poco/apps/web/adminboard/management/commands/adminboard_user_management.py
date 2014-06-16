import sys
import datetime
import random
import hashlib
from django.core.management.base import BaseCommand, CommandError
from common.mongo_client import getMongoClient


mongo_client = getMongoClient()

# http://www.aspheute.com/english/20040105.asp
def createRandomPassword(length):
    allowedChars = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNOPQRSTUVWXYZ23456789"
    password = ""
    for i in range(length):
        password += allowedChars[random.randint(0, 256) % len(allowedChars)]
    return password

def createHashedPassword(password):
    salt = createRandomPassword(16)
    hashed_password = hashlib.sha256(password + salt).hexdigest()
    return hashed_password, salt



c_admin_users = mongo_client.getTjbDb()["admin-users"]

#random.seed(open("/dev/random", "rb").read(10))
random.seed(str(datetime.datetime.now()))


def cmd_createNewUser():
    while True:
        user_name = raw_input("name:")
        if c_admin_users.find_one({"user_name": user_name}) is None:
            break
        else:
            print "user already exists."
    

    password = createRandomPassword(10)
    print "password is:", password

    hashed_password, salt = createHashedPassword(password)

    c_admin_users.insert({"user_name": user_name, "hashed_password": hashed_password, "salt": salt})


def _enterExistedUser():
    while True:
        user_name = raw_input("name:")
        user_in_db = c_admin_users.find_one({"user_name": user_name})
        if user_in_db is not None:
            break
        else:
            print "user does not exist."
    return user_in_db


def cmd_generateNewPassword():
    user = _enterExistedUser()

    password = createRandomPassword(10)
    print "password is:", password

    hashed_password, salt = createHashedPassword(password)
    
    c_admin_users.update({"user_name": user["user_name"]}, \
            {"$set": {"hashed_password": hashed_password, "salt": salt}})


def cmd_showUserInfo():
    user = _enterExistedUser()
    print user


class Command(BaseCommand):
    args = ''
    help = 'The User Management Utility for Admin Board'

    def handle(self, *args, **options):
        while True:
            print "1. create New User"
            print "2. generate New Password"
            print "3. show user info"
            cmd = raw_input("enter a number:").strip()
            if cmd == "1":
                cmd_createNewUser()
            elif cmd == "2":
                cmd_generateNewPassword()
            elif cmd == "3":
                cmd_showUserInfo()
