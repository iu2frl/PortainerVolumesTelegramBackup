import os
import logging
from datetime import datetime
import time
import tarfile
import telebot
import requests
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

try:
    LOG_FILE_NAME = datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
    logging.basicConfig(filename=f"/tmp/{LOG_FILE_NAME}", level=logging.DEBUG)
    LOG_FILE_NAME = f"/tmp/{LOG_FILE_NAME}"
except Exception as retEx:
    logging.error("Cannot create log file: [%s]. Defaulting to current folder", str(retEx))
    logging.basicConfig(filename=LOG_FILE_NAME, level=logging.DEBUG)

TELEGRAM_API_TOKEN: str = os.environ.get('BOT_TOKEN')
if not TELEGRAM_API_TOKEN:
    logging.critical("Input token is empty!")
    raise ValueError("Invalid BOT_TOKEN")
else:
    logging.debug("BOT_TOKEN length: [%s]", len(TELEGRAM_API_TOKEN))

# Get destination chat
TELEGRAM_DEST_CHAT: str = os.environ.get('BOT_DEST')
if not TELEGRAM_DEST_CHAT:
    logging.critical("Destination chat is empty!")
    raise ValueError("Invalid BOT_DEST")
else:
    TELEGRAM_DEST_CHAT: int = int(TELEGRAM_DEST_CHAT)
    logging.debug("BOT_DEST: [%s]", TELEGRAM_DEST_CHAT)

bot = telebot.TeleBot(TELEGRAM_API_TOKEN)

# Custom message to send before files list
TELEGRAM_BACKUP_MESSAGE: str = os.environ.get('CUST_MSG')
if not TELEGRAM_BACKUP_MESSAGE:
    TELEGRAM_BACKUP_MESSAGE = "Backup at " + datetime.now().strftime("%Y%m%d_%H%M%S")
else:
    TELEGRAM_BACKUP_MESSAGE += "\n\nBackup at " + datetime.now().strftime("%Y%m%d_%H%M%S")

# Get volumes root path
DOCKER_VOLUME_DIRECTORIES: str = os.environ.get('ROOT_DIR')
if not DOCKER_VOLUME_DIRECTORIES:
    # Common volumes locations
    DOCKER_VOLUME_DIRECTORIES = ["/var/snap/docker/common/var-lib-docker/volumes/", "/var/lib/docker/volumes", "/root/backup"]
    logging.warning("ROOT_DIR is empty, falling back to default path(s): %s", DOCKER_VOLUME_DIRECTORIES)
else:
    # Get directories from environment
    DOCKER_VOLUME_DIRECTORIES = [str(x).strip() for x in DOCKER_VOLUME_DIRECTORIES.split(",")]
    logging.debug("ROOT_DIR: [%s]", DOCKER_VOLUME_DIRECTORIES)

# Get temporary path
TMP_DIR: str = os.environ.get('TMP_DIR')
if not TMP_DIR:
    TMP_DIR = "/tmp"
    logging.warning("TMP_DIR is empty, falling back to default path: [%s]", TMP_DIR )
TMP_DIR = os.path.join(TMP_DIR, datetime.now().strftime("%Y%m%d_%H%M%S"))
if not os.path.exists(TMP_DIR):
    try:
        os.mkdir(TMP_DIR)
    except Exception as retEx:
        logging.error("Cannot create temporary folder: [%s]. Defaulting to current folder", str(retEx))
        TMP_DIR = os.getcwd()
logging.debug("TMP_DIR: [%s]", TMP_DIR)

PORTAINER_API_URL = os.environ.get('BACKUP_API_URL')
if not PORTAINER_API_URL:
    logging.critical("PORTAINER_API_URL is empty!")
    raise ValueError("Invalid PORTAINER_API_URL")
logging.debug("PORTAINER_API_URL: [%s]", PORTAINER_API_URL)

PORTAINER_API_KEY = os.environ.get('API_KEY')
if not PORTAINER_API_KEY:
    logging.critical("API_KEY is empty!")
    raise ValueError("Invalid API_KEY")
logging.debug("API_KEY length: [%s]", len(PORTAINER_API_KEY))

# Maximum upload size (in MB) for a single Telegram document.
# Archives bigger than this are split into smaller parts before sending.
MAX_UPLOAD_SIZE_MB = os.environ.get('MAX_UPLOAD_SIZE')
if not MAX_UPLOAD_SIZE_MB:
    MAX_UPLOAD_SIZE_MB = 50
    logging.warning("MAX_UPLOAD_SIZE is empty, falling back to default: [%s] MB", MAX_UPLOAD_SIZE_MB)
else:
    try:
        MAX_UPLOAD_SIZE_MB = int(MAX_UPLOAD_SIZE_MB)
        if MAX_UPLOAD_SIZE_MB <= 0:
            raise ValueError("MAX_UPLOAD_SIZE must be a positive integer")
    except ValueError:
        logging.error("MAX_UPLOAD_SIZE is not a valid positive integer, falling back to default: 50 MB")
        MAX_UPLOAD_SIZE_MB = 50
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
logging.debug("MAX_UPLOAD_SIZE: [%s] MB ([%s] bytes)", MAX_UPLOAD_SIZE_MB, MAX_UPLOAD_SIZE)

PORTAINER_BACKUP_FILE = os.path.join(TMP_DIR, "portainer_backup.tar.gz")
logging.debug("PORTAINER_BACKUP_FILE: [%s]", PORTAINER_BACKUP_FILE)

# Function to compress a folder
def MakeTar(source_dir, output_filename):
    logging.debug("Compressing: [%s] to: [%s]", source_dir, output_filename)
    try:
        with tarfile.open(output_filename, "w:xz") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir))
        return True
    except Exception as ret_exc:
        logging.error("Failed to compress [%s] to [%s]: [%s]", source_dir, output_filename, str(ret_exc))
        return False

def split_file(file_path, chunk_size):
    """Split a file into chunks of at most chunk_size bytes.

    Parts are named "<file_path>.000", "<file_path>.001", ... (zero-padded,
    in order). They can be recombined at restore time by concatenating them
    in alphabetical/numerical order, e.g.:
        cat archive.tar.xz.* > archive.tar.xz
    Returns the list of generated part paths, or an empty list on failure.
    """
    part_paths = []
    try:
        with open(file_path, 'rb') as src:
            index = 0
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                part_path = "%s.%03d" % (file_path, index)
                with open(part_path, 'wb') as dst:
                    dst.write(chunk)
                part_paths.append(part_path)
                logging.debug("Created split part: [%s] (%d bytes)", part_path, len(chunk))
                index += 1
        return part_paths
    except Exception as ret_exc:
        logging.error("Failed to split [%s]: [%s]", file_path, str(ret_exc))
        # Clean up any partial parts that were created
        for part_path in part_paths:
            try:
                os.remove(part_path)
            except OSError:
                pass
        return []

def send_document_with_retries(file_path, attempts=3):
    """Send a single file as a Telegram document, retrying on transient errors.

    Returns True if the document was sent successfully, False otherwise.
    """
    for attempt in range(attempts):
        try:
            with open(file_path, 'rb') as f:
                bot.send_document(TELEGRAM_DEST_CHAT, f)
            logging.debug("Document: [%s] was sent succesfully", file_path)
            return True
        except Exception as retEx:
            error_str = str(retEx)
            if "413" in error_str or "Request Entity Too Large" in error_str:
                logging.error("Cannot send document: [%s]", retEx)
                try:
                    bot.send_message(TELEGRAM_DEST_CHAT, "Cannot send document `" + file_path + "`: [" + str(retEx) + "]")
                except Exception as sendEx:
                    logging.error("Failed to send error message: [%s]", sendEx)
                return False
            if attempt < attempts - 1:
                logging.warning("Failed to send document, retrying in 5 seconds... (%d/%d)", attempt + 1, attempts)
                time.sleep(5)
            else:
                logging.error("Cannot send document after %d attempts: [%s]", attempts, retEx)
                try:
                    bot.send_message(TELEGRAM_DEST_CHAT, "Cannot send document `" + file_path + "`: [" + str(retEx) + "]")
                except Exception as sendEx:
                    logging.error("Failed to send error message: [%s]", sendEx)
    return False

def send_archive(file_path):
    """Send a file to Telegram, splitting it into parts if it exceeds the
    configured upload limit.

    If the file is small enough it is sent as-is. Otherwise it is split into
    "<file_path>.NNN" parts that are sent individually; each part is removed
    after a successful send. Returns True only if the file (and all of its
    parts) were sent successfully.
    """
    try:
        file_size = os.path.getsize(file_path)
    except OSError as ret_exc:
        logging.error("Cannot get size of [%s]: [%s]", file_path, str(ret_exc))
        return False

    if file_size <= MAX_UPLOAD_SIZE:
        return send_document_with_retries(file_path)

    logging.info(
        "Archive [%s] (%d bytes) exceeds upload limit (%d bytes), splitting into parts",
        file_path, file_size, MAX_UPLOAD_SIZE
    )
    part_paths = split_file(file_path, MAX_UPLOAD_SIZE)
    if not part_paths:
        logging.error("Cannot split: [%s]", file_path)
        return False

    all_sent = True
    for part_path in part_paths:
        if send_document_with_retries(part_path):
            try:
                os.remove(part_path)
                logging.debug("Part: [%s] was deleted succesfully", part_path)
            except Exception as retEx:
                logging.error("Error while deleting part [%s]: [%s]", part_path, retEx)
        else:
            all_sent = False
    return all_sent


    """Request a backup from Portainer and save it to output_file"""
    try:
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json; charset=utf-8"
        }
        data = {
            "password": ""
        }
        response = requests.post(api_url, headers=headers, json=data, verify=False, timeout=10)
        if response.status_code == 200:
            with open(output_file, 'wb') as f:
                f.write(response.content)
            logging.info("Portainer backup saved to: [%s]", output_file)
            return True
        else:
            logging.error("Failed to request Portainer backup: [%s]", response.text)
            return False
    except Exception as e:
        logging.error("Failed to request Portainer backup: [%s]", str(e))
        return False

if __name__ == '__main__':
    # Send custom message
    bot.send_message(TELEGRAM_DEST_CHAT, TELEGRAM_BACKUP_MESSAGE)
    # Create temporary output path
    if not os.path.exists(TMP_DIR):
        logging.info("Creating: [%s] folder", TMP_DIR)
        os.mkdir(TMP_DIR)
    else:
        logging.warning("Folder: [%s] already exists, this could cause some troubles", TMP_DIR)
    # Process path(s) list
    for singleLocation in DOCKER_VOLUME_DIRECTORIES:
        try:
            # Check if we can access that folder
            subFolders = os.listdir(singleLocation)
        except FileNotFoundError:
            logging.warning("Cannot access path: [%s]", singleLocation)
            continue
        # If the path exists
        for singleSubfolder in subFolders:
            folderToCompress = os.path.join(singleLocation, singleSubfolder)
            # Check if it is a folder
            if os.path.isdir(folderToCompress):
                logging.debug("Found valid folder: %s", folderToCompress)
                archiveName = singleSubfolder + "-" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".tar.xz"
                outputPath = os.path.join(TMP_DIR, archiveName)
                if (MakeTar(folderToCompress, outputPath)):
                    logging.info("Succesfully compressed: [%s]", outputPath)
                    # Send archive (split into parts if it exceeds the upload limit)
                    sent = send_archive(outputPath)
                    if sent:
                        # Delete archive
                        try:
                            os.remove(outputPath)
                            logging.debug("File: [%s] was deleted succesfully", outputPath)
                        except Exception as retEx:
                            logging.error("Error while deleting: [%s]", retEx)
                else:
                    logging.error("Cannot compress: [%s]", outputPath)
    # Send log file
    for attempt in range(3):
        try:
            with open(LOG_FILE_NAME, 'rb') as f:
                bot.send_document(TELEGRAM_DEST_CHAT, f)
            logging.debug("Backup file sent")
            break
        except Exception as retEx:
            error_str = str(retEx)
            if "413" in error_str or "Request Entity Too Large" in error_str:
                logging.error("Error while sending log file: [%s]", retEx)
                break
            if attempt < 2:
                logging.warning("Failed to send log file, retrying in 5 seconds... (%d/3)", attempt + 1)
                time.sleep(5)
            else:
                logging.error("Error while sending log file after 3 attempts: [%s]", retEx)

    # Request and send Portainer backup
    if request_portainer_backup(PORTAINER_API_URL, PORTAINER_API_KEY, PORTAINER_BACKUP_FILE):
        send_archive(PORTAINER_BACKUP_FILE)
    else:
        bot.send_message(TELEGRAM_DEST_CHAT, "Failed to request Portainer backup")
        logging.error("Failed to request Portainer backup")

    # Done, bye!
    logging.info("Completed!")
