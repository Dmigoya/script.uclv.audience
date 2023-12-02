import xbmc
import xbmcgui
import xbmcaddon
import json
import requests
import os
from datetime import datetime
import shutil
import uuid
import subprocess
import glob

# globals
addon = xbmcaddon.Addon()
jwt = ''

# Configs
def getSetting(key):
    return addon.getSetting(key)

def getBoolSetting(key):
    return addon.getSetting(key).lower() == "true"

def getIntSetting(key):
    return int(addon.getSetting(key))

# View
def notification(title, message, time):
    if getBoolSetting('isDebug'):
        dialog = xbmcgui.Dialog()
        dialog.notification(title, message, xbmcgui.NOTIFICATION_INFO, time)


def dialog(title, message):
    if getBoolSetting('isDebug'):
        dialog = xbmcgui.Dialog()
        dialog.ok(title, message)


def dialogYesNoCopyFileDataToUSB(title, message, pathUSB):
    if getBoolSetting('isDebug'):
        dialog = xbmcgui.Dialog()
        isPressedYes = dialog.yesno(title, message)
        if isPressedYes:
            return copyDataFile(pathUSB)
        else:
            return False
    else:
        return copyDataFile(pathUSB)


def dialogYesNoRemovedFileData(title, message):
    flag = False
    if getBoolSetting('isDebug'):
        dialog = xbmcgui.Dialog()
        flag = dialog.yesno(title, message)
    else:
        flag = getBoolSetting('removeDataWhenCopyToUSB')
    if flag:
        removeDataFile()
    return flag


# Data
def writeData(data):
    if not isSpaceAvailable():
        notification('Audiometer', 'No hay espacio en el disco', 10000)
        return
    path = os.path.join(xbmcaddon.Addon().getAddonInfo('path'), getSetting('data_name_file'))

    fileJson = readData()
    if fileJson is not None and 'data' in fileJson:
        fileJson['data'].append(data)
    else:
        fileJson = {'data': []}
        fileJson['data'].append(data)

    with open(path, 'w') as f:
        json.dump(fileJson, f)


def readData():
    path = os.path.join(xbmcaddon.Addon().getAddonInfo('path'), getSetting('data_name_file'))
    try:
        with open(path) as f:
            return json.load(f)
    except IOError, e:
        data = {}
        with open(path, 'w') as f:
            json.dump(data, f)
        return data


def getModelDataToSave(name, timeIn):
    data = {}
    data['name'] = name
    data['time_in'] = timeIn.strftime('%Y-%m-%dT%H:%M:%S.%f')
    data['time_out'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
    return data


def removeDataFile():
    path = os.path.join(xbmcaddon.Addon().getAddonInfo('path'), getSetting('data_name_file'))
    if os.path.exists(path):
        os.remove(path)


def existDataFile():
    path = os.path.join(xbmcaddon.Addon().getAddonInfo('path'), getSetting('data_name_file'))
    return os.path.exists(path)

def existFile(dir, start_name):
    regex = "{}{}*".format(dir+'/', start_name)
    files_found = glob.glob(regex)
    return len(files_found) > 0


def copyDataFile(pathEnd):
    try:
        current_date_time = datetime.now().strftime("%Y%m%d_%H%M%S")

        uuid_str = getUUID()
        original_name = getSetting('data_name_file')
        base_name, extension = original_name.rsplit('.', 1)
        new_name = "{}_{}_{}.{}".format(base_name, uuid_str, current_date_time, extension)
        if existFile(pathEnd, "{}_{}".format(base_name, uuid_str)):
            return True

        pathIn = os.path.join(xbmcaddon.Addon().getAddonInfo('path'), original_name)
        pathEndComplete = os.path.join(pathEnd, new_name)
        shutil.copy(pathIn, pathEndComplete)
        return True
    except Exception, e:
        return False


def isSpaceAvailable():
    path = xbmcaddon.Addon().getAddonInfo('path')
    dataFile = getSetting('data_name_file')
    pathPlusDataFile = os.path.join(path, dataFile)
    if os.path.exists(path):
        statvfs = os.statvfs(path)
        freeSpace = statvfs.f_bavail * statvfs.f_frsize
        if os.path.exists(pathPlusDataFile):
            sizeFile = os.path.getsize(pathPlusDataFile)
            freeSpace -= sizeFile
        if freeSpace > getIntSetting("max_space_kb"):
            return True
        else:
            return False
    else:
        return False


def findUSB():
    usbName = getSetting('usbName')
    result = subprocess.Popen(['df'], stdout=subprocess.PIPE)
    stdout, _ = result.communicate()
    lines = stdout.split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) > 0 and '/' in parts[-1] and usbName == parts[-1].split('/')[-1]:
            return parts[-1]
    return ''


def getUUID():
    return str(uuid.getnode())


# API
def getTokenJWT():
    urlbase = getSetting("url_api") + ":" + getSetting("port_api")
    url = urlbase + "/api/v1/login"

    payload = json.dumps({
        "userName": getSetting('userName'),
        "password": getSetting('password')
    })
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            return response.json()['token']
        else:
            notification("Audiometer", "Error al obtener token JWT: {}".format(response.status_code), 5000)
            return ''
    except Exception, e:
        return ''


def sendData():
    if not existDataFile():
        return True
    baseUrl = getSetting("url_api") + ":" + getSetting("port_api")
    url = baseUrl + "/api/v1/data/saveData"
    payload = readData()
    global jwt
    token = jwt
    if token == '':
        token = getTokenJWT()
        if token == '':
            return False
        else:
            jwt = token
    token = "Bearer " + token

    headers = {
        "Authorization": token,
        'Content-Type': 'application/json'}

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == 200:
            if getBoolSetting('removeDataWhenSendToServer'):
                removeDataFile()
            return True
        else:
            if response.text == 'Invalid token':
                jwt = ''
                sendData()
    except Exception, e:
        return False


def copyToUSBLogic():
    if not existDataFile():
        return
    pathUSB = findUSB()
    if pathUSB != '':
        copied = dialogYesNoCopyFileDataToUSB("Audiometer", "Copiar los datos registrados en la USB", pathUSB)
        if copied:
            deleted = dialogYesNoRemovedFileData("Audiometer", "Eliminar los datos ya copiados")
            if deleted:
                notification("Audiometer", "Datos copiados y eliminados", 5000)
            else:
                notification("Audiometer", "Datos copiados", 5000)
        else:
            notification("Audiometer", "Error al copiar los datos", 5000)


# test-------------------------------------------------------------------------

# main-------------------------------------------------------------------------
notification("Audiometer", "The addon is running", 5000)
timeIn = datetime.now()
flagSaveDone = True
name = ''

# logic
while True:
    sleep_time = getIntSetting("sleep_time")
    if xbmc.Player().isPlaying():
        flagSaveDone = False
        if name == '':
            name = xbmc.getInfoLabel("Player.Title")
            timeIn = datetime.now()
            xbmc.sleep(1000 * sleep_time)
            continue
        if xbmc.getInfoLabel("Player.Title") != name:
            data = getModelDataToSave(name, timeIn)
            writeData(data)
            name = xbmc.getInfoLabel("Player.Title")
            timeIn = datetime.now()
            xbmc.sleep(1000 * sleep_time)
            continue
    else:
        if not flagSaveDone:
            data = getModelDataToSave(name, timeIn)
            writeData(data)
            name = ''
            flagSaveDone = True
            xbmc.sleep(1000 * sleep_time)
            continue
    if not sendData():
        copyToUSBLogic()

# duration = xbmc.getInfoLabel("Player.Time")
# videoFormat = xbmc.getInfoLabel("Player.VideoCodec")
# audioFormat = xbmc.getInfoLabel("Player.AudioCodec")
