import re
import ssl
import base64
from socket import *

SERVER_ADDRESSES = {
    b"yandex": ("smtp.yandex.ru", 465),
    b"mail": ("smtp.mail.ru", 465),
    b"rambler": ("smtp.rambler.ru", 465)
}

DIRECTORY = "письмо\\"
LETTER_FILE = DIRECTORY + "letter.txt"
CONFIG_FILE = DIRECTORY + "config.txt"
TIMEOUT = 5


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


def parse_server(login: bytes):
    start = login.find(b'@') + 1
    if start == 0 or start == 2:
        print("INCORRECT LOGIN!")
        sys.exit()
    return login[start:].split(b'.')[0]


def get_ssl_socket_connection(address):
    sock = socket()
    sock.settimeout(TIMEOUT)
    sock.connect(address)
    sock = ssl.wrap_socket(sock)
    return sock


def send_recv(sock: socket, command: bytes):
    sock.send(command)
    data = sock.recv(1024)
    print(data)
    return data


class SMTPClient:
    def __init__(self, login: bytes, password: bytes):
        self.login = login
        self.password = password
        self.server = parse_server(login)
        self.server_address = SERVER_ADDRESSES[self.server]
        self.sock = get_ssl_socket_connection(self.server_address)
        print(self.sock.recv(1024))
        self.greet_server()

    def greet_server(self):
        send_recv(self.sock, b'EHLO %s\r\n' % self.login)
        send_recv(self.sock, b"AUTH LOGIN\r\n")
        encode_login = base64.b64encode(self.login) + b'\r\n'
        encode_password = base64.b64encode(self.password) + b'\r\n'
        send_recv(self.sock, encode_login)
        send_recv(self.sock, encode_password)

    def send(self, letter):
        send_recv(self.sock, b"MAIL FROM: <" + self.login + b">\r\n")  # ящик в скобки <>
        for recipient in letter.recipients:
            send_recv(self.sock, b"RCPT TO: <" + recipient.encode() + b">\r\n")
        data = letter.generate_letter(self.login)
        send_recv(self.sock, b"DATA\r\n")
        send_recv(self.sock, data)

    def finish_connection(self):
        send_recv(self.sock, b"QUIT\r\n")
        self.sock.close()


def main():
    login = input("LOGIN: ").encode()
    login = b"testtesttest100500@yandex.ru"
    password = input("PASSWORD: ").encode()
    password = b"12345678901234567890"
    client = SMTPClient(login, password)
    letter = get_letter_from_files()
    client.send(letter)


if __name__ == "__main__":
    main()
