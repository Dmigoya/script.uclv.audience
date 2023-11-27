import xbmc
import xbmcgui
import json
import requests
import os
from datetime import datetime
import shutil
import uuid
import subprocess
import glob

# globals
configPath = '/Users/davidmigoya/Library/Application Support/Kodi/addons/script.uclv.audience/config.json'
jwt = ''


# View
def notification(title, message, time):
    configs = readConfigs()
    if configs['isDebug']:
        dialog = xbmcgui.Dialog()
        dialog.notification(title, message, xbmcgui.NOTIFICATION_INFO, time)


def dialog(title, message):
    configs = readConfigs()
    if configs['isDebug']:
        dialog = xbmcgui.Dialog()
        dialog.ok(title, message)


def dialogYesNoCopyFileDataToUSB(title, message, pathUSB):
    configs = readConfigs()
    if configs['isDebug']:
        dialog = xbmcgui.Dialog()
        isPressedYes = dialog.yesno(title, message)
        if isPressedYes:
            return copyDataFile(pathUSB)
        else:
            return False
    else:
        return copyDataFile(pathUSB)


def dialogYesNoRemovedFileData(title, message):
    configs = readConfigs()
    flag = False
    if configs['isDebug']:
        dialog = xbmcgui.Dialog()
        flag = dialog.yesno(title, message)
    else:
        flag = configs['removeDataWhenCopyToUSB']
    if flag:
        removeDataFile()
    return flag


# Data
def readConfigs():
    global configPath
    try:
        with open(configPath) as f:
            return json.load(f)
    except Exception, e:
        notification("Audiometer", "Error al leer configuraciones: {}".format(e), 5000)
        return {}


def writeData(data):
    if not isSpaceAvailable():
        notification('Audiometer', 'No hay espacio en el disco', 10000)
        return
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    fileJson = readData()
    if fileJson is not None and 'data' in fileJson:
        fileJson['data'].append(data)
    else:
        fileJson = {'data': []}
        fileJson['data'].append(data)

    with open(path, 'w') as f:
        json.dump(fileJson, f)


def readData():
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
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
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    if os.path.exists(path):
        os.remove(path)


def existDataFile():
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    return os.path.exists(path)

def existFile(dir, start_name):
    regex = "{}{}*".format(dir+'/', start_name)
    files_found = glob.glob(regex)
    return len(files_found) > 0


def copyDataFile(pathEnd):
    configs = readConfigs()
    try:
        current_date_time = datetime.now().strftime("%Y%m%d_%H%M%S")

        uuid_str = getUUID()
        original_name = configs['data_name_file']
        base_name, extension = original_name.rsplit('.', 1)
        new_name = "{}_{}_{}.{}".format(base_name, uuid_str, current_date_time, extension)
        if existFile(pathEnd, "{}_{}".format(base_name, uuid_str)):
            return True

        pathIn = configs['master_path'] + original_name
        pathEndComplete = pathEnd + '/' + new_name

        shutil.copy(pathIn, pathEndComplete)
        return True
    except Exception, e:
        return False


def isSpaceAvailable():
    configs = readConfigs()
    path = configs['master_path']
    dataFile = configs['data_name_file']
    if os.path.exists(path):
        statvfs = os.statvfs(path)
        freeSpace = statvfs.f_bavail * statvfs.f_frsize
        if os.path.exists(path + dataFile):
            sizeFile = os.path.getsize(path + dataFile)
            freeSpace -= sizeFile
        if freeSpace > configs["max_space_kb"]:
            return True
        else:
            return False
    else:
        return False


def findUSB():
    configs = readConfigs()
    usbName = configs['usbName']
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
    configs = readConfigs()
    urlbase = configs["url_api"] + ":" + configs["port_api"]
    url = urlbase + "/api/v1/login"

    payload = json.dumps({
        "userName": configs['userName'],
        "password": configs['password']
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
        notification("Audiometer", "Error en la solicitud de JWT: {}".format(e), 5000)
        return ''


def sendData():
    if not existDataFile():
        return True
    configs = readConfigs()
    baseUrl = configs["url_api"] + ":" + configs["port_api"]
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
            if configs['removeDataWhenSendToServer']:
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
configs = readConfigs()
timeIn = datetime.now()
flagSaveDone = True
name = ''

# logic
while True:
    if xbmc.Player().isPlaying():
        flagSaveDone = False
        if name == '':
            name = xbmc.getInfoLabel("Player.Title")
            timeIn = datetime.now()
            xbmc.sleep(1000 * configs["sleep_time"])
            continue
        if xbmc.getInfoLabel("Player.Title") != name:
            data = getModelDataToSave(name, timeIn)
            writeData(data)
            name = xbmc.getInfoLabel("Player.Title")
            timeIn = datetime.now()
            xbmc.sleep(1000 * configs["sleep_time"])
            continue
    else:
        if not flagSaveDone:
            data = getModelDataToSave(name, timeIn)
            writeData(data)
            name = ''
            flagSaveDone = True
            xbmc.sleep(1000 * configs["sleep_time"])
            continue
    if not sendData():
        copyToUSBLogic()

# duration = xbmc.getInfoLabel("Player.Time")
# videoFormat = xbmc.getInfoLabel("Player.VideoCodec")
# audioFormat = xbmc.getInfoLabel("Player.AudioCodec")
