from django.core.management.base import BaseCommand, CommandError
from common.mongo_client import getMongoClient
import random
import hashlib
from django.conf import settings


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


mongo_client = getMongoClient()

c_users = mongo_client.getTjbDb()["users"]

random.seed(open("/dev/random", "rb").read(10))


def _inputSites():
    sites_str = raw_input("sites(comma separated):").strip()
    if sites_str == "":
        return []
    else:
        return sites_str.split(",")


def cmd_createNewUser():
    while True:
        user_name = raw_input("name:")
        if c_users.find_one({"user_name": user_name}) is None:
            break
        else:
            print "user already exists."
    
    sites = _inputSites()

    password = createRandomPassword(10)
    print "password is:", password

    hashed_password, salt = createHashedPassword(password)

    c_users.insert({"user_name": user_name, "hashed_password": hashed_password, "salt": salt,
                  "sites": sites, "is_admin": False})


def _enterExistedUser():
    while True:
        user_name = raw_input("name:")
        user_in_db = c_users.find_one({"user_name": user_name})
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
    
    c_users.update({"user_name": user["user_name"]}, \
            {"$set": {"hashed_password": hashed_password, "salt": salt}})

def cmd_updateSite():
    user = _enterExistedUser()
    sites = _inputSites()
    c_users.update({"user_name": user["user_name"]}, {"$set": {"sites": sites}})

def cmd_addSite():
    user = _enterExistedUser()
    sites = user["sites"]
    sites = sites + _inputSites()
    sites = list(set(sites))
    sites.sort()
    c_users.update({"user_name": user["user_name"]}, {"$set": {"sites": sites}})

def cmd_showUserInfo():
    user = _enterExistedUser()
    print user

def cmd_listUsers():
    for user in c_users.find():
        print "IsAdmin:%s" % user.get("is_admin", False), "User Name:%s" % user["user_name"], "Managed Sites:%s" % (user["sites"],)

def cmd_promoteAdmin():
    user = _enterExistedUser()
    if raw_input("WARNING: you are about to promote %s as admin.(yes to continue)" % user["user_name"]) == "yes":
        c_users.update({"user_name": user["user_name"]}, {"$set": {"is_admin": True}})
    else:
        print "the action cancelled."


class Command(BaseCommand):
    args = ''
    help = 'The User Management Utility for Dashboard'

    def handle(self, *args, **options):
        while True:
            print "1. create New User"
            print "2. generate New Password"
            print "3. update managed sites"
            print "4. add managed sites"
            print "5. show user info"
            print "6. list users"
            print "7. promote user as admin"
            cmd = raw_input("enter a number:").strip()
            if cmd == "1":
                cmd_createNewUser()
            elif cmd == "2":
                cmd_generateNewPassword()
            elif cmd == "3":
                cmd_updateSite()
            elif cmd == "4":
                cmd_addSite()   
            elif cmd == "5":
                cmd_showUserInfo()
            elif cmd == "6":
                cmd_listUsers()
            elif cmd == "7":
                cmd_promoteAdmin()

        self.stdout.write("Exit.")
