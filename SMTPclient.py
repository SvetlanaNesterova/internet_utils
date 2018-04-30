import re
import ssl
import base64
from socket import *

SERVER_ADDRESSES = {
    "yandex": ("smtp.yandex.ru", 465),
    "mail": ("smtp.mail.ru", 465),
    "rambler": ("smtp.rambler.ru", 465)
}

DIRECTORY = "письмо\\"
LETTER_FILE = DIRECTORY + "letter.txt"
CONFIG_FILE = DIRECTORY + "config.txt"
TIMEOUT = 6


class Letter:
    def __init__(self):
        self.text = None
        self.subject = None
        self.recipients = []
        self.attachments = []

    def generate_letter(self, sender: bytes) -> bytes:
        text = add_escapes_to_text(self.text)
        boundary = self.generate_boundary()
        header = b'From: %s\r\n' % sender + \
                 b'To: %s\r\n' % ', '.join(self.recipients).encode() + \
                 b'Subject: %s\r\n' % self.subject.encode()[:-1]
        headers_and_text_plain = \
            b'MIME-Version: 1.0\r\n' \
            b'Content-Type: multipart/mixed; boundary="%s"\r\n\r\n' % boundary + \
            b'\r\n' \
            b'--%s\r\n' % boundary + \
            b'Content-Type: text/plain\r\n' \
            b'\r\n' \
            b'%s' % text
        attachments = self.convert_attachments(boundary)
        ending = b'\r\n--%s--\r\n' % boundary + \
                 b'.\r\n'
        return header + headers_and_text_plain + attachments + ending

    def generate_boundary(self) -> bytes:
        return b'boundary1q2w3e4r5t6y7u8i9o0pboundary'

    def convert_attachments(self, boundary: bytes) -> bytes:
        parts = []
        for name, data in self.attachments:
            parts.append(b"\r\n--%s\r\n" % boundary)
            header = b'Content-Disposition: attachment;	filename="%s"\r\n' % name + \
                     b'Content-Transfer-Encoding: base64\r\n' + \
                     b'Content-Type: application/octet-stream; name="%s"\r\n\r\n' % name
            parts.append(header)
            parts.append(base64.b64encode(data))
        return b''.join(parts)


def add_escapes_to_text(text: bytes) -> bytes:
    if text[0] == b'.':
        text = b'.' + text
    return re.sub(b"\n\.", b"\n..", text)


def get_letter_from_files() -> Letter:
    letter = Letter()
    with open(LETTER_FILE, 'rb') as f:
        letter.text = f.read()
    with open(CONFIG_FILE, 'rb') as f:
        config = f.read().decode()
    letter.recipients, letter.subject, letter.attachments = parse_config(config)
    load_attachments(letter)
    return letter


def parse_config(config: str):
    to_start = config.find("TO:")
    subject_start = config.find("SUBJECT:")
    attachments_start = config.find("ATTACHMENTS:")
    if to_start == -1 or subject_start == -1 or attachments_start == -1 \
            and not (to_start < subject_start < attachments_start):
        raise ValueError("Incorrect config file")
    to = config[to_start + len("TO:\r\n"):subject_start].split('\r\n')
    subject = config[subject_start + len("SUBJECT:\r\n"):attachments_start]
    attachments = config[attachments_start+len("ATTACHMENTS:\r\n"):].split("\r\n")
    return to, subject, attachments


def load_attachments(letter):
    letter.attachments = [(name.encode(), load_file(name)) for name in letter.attachments if name != ""]


def load_file(file_name):
    with open(DIRECTORY + file_name, 'rb') as file:
        data = file.read()
    return data


def check_login_and_parse_server(login: str):
    m = re.match('([-a-z0-9_.]+)@([-a-z0-9]+)\.([a-z]{2,6})', login)
    if not m:
        return False
    return m.groups()[1]


def get_ssl_socket_connection(address):
    sock = socket()
    sock.settimeout(TIMEOUT)
    sock.connect(address)
    sock = ssl.wrap_socket(sock)
    return sock


def send_recv(sock: socket, command: bytes):
    try:
        sock.send(command)
        data = sock.recv(1024)
    except Exception as e:
        return b"Connection error " + str(e).encode()
    return data


class SMTPClient:
    def __init__(self, login, password):
        self.login = login.encode()
        self.password = password.encode()
        self.server = check_login_and_parse_server(login)
        if not self.server:
            raise Exception("Incorrect login")
        if self.server not in SERVER_ADDRESSES:
            raise Exception("Client does not send letters from the mailboxes of this domain")
        self.server_address = SERVER_ADDRESSES[self.server]
        self.sock = get_ssl_socket_connection(self.server_address)
        answer = self.sock.recv(1024)
        if not answer.startswith(b"2"):
            raise Exception(answer.decode())
        self.greet_server()
        self.introduce()

    def send_command_sequence(self, commands):
        i = 0
        prev_bad_command = -1
        while i < len(commands):
            command = commands[i]
            answer = send_recv(self.sock, command)
            if answer.startswith(b"4"):
                if prev_bad_command != i:
                    prev_bad_command = i
                    i = 0
                    continue
            if not answer.startswith(b"2") and not answer.startswith(b"3"):
                raise Exception(answer.decode())
            i += 1

    def greet_server(self):
        command_seq = [
            b'EHLO %s\r\n' % self.login
        ]
        self.send_command_sequence(command_seq)

    def introduce(self):
        encode_login = base64.b64encode(self.login) + b'\r\n'
        encode_password = base64.b64encode(self.password) + b'\r\n'
        command_seq = [
            b"AUTH LOGIN\r\n",
            encode_login,
            encode_password
            ]
        self.send_command_sequence(command_seq)

    def send(self, letter):
        command_seq = [b"MAIL FROM: <" + self.login + b">\r\n"]
        for recipient in letter.recipients:
            if recipient:
                command_seq.append(b"RCPT TO: <" + recipient.encode() + b">\r\n")
        data = letter.generate_letter(self.login)
        command_seq.append(b"DATA\r\n")
        command_seq.append(data)
        self.send_command_sequence(command_seq)

    def finish_connection(self):
        send_recv(self.sock, b"QUIT\r\n")
        self.sock.close()


def main():
    while True:
        login = input("LOGIN: ")
        login = "testtesttest100500@yandex.ru"
        password = input("PASSWORD: ")
        password = "12345678901234567890"
        try:
            client = SMTPClient(login, password)
        except Exception as e:
            print(str(e))
            continue
        break
    print("Authentication was successful")
    try:
        letter = get_letter_from_files()
    except Exception as e:
        print(str(e))
        return
    print("Letter was formed")
    try:
        client.send(letter)
    except Exception as e:
        print(str(e))
        return
    print("Letter was sent")


if __name__ == "__main__":
    main()
