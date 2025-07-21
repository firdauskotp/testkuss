import gridfs, io, os, json, smtplib, base64
from urllib.parse import urlencode
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify, Response
from flask_pymongo import MongoClient
from werkzeug.security import check_password_hash
from flask_mail import Mail, Message
from datetime import datetime
import certifi  # Only needed for Mac
from werkzeug.utils import secure_filename
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from bson import ObjectId, json_util
from .utils import log_activity, safe_int, send_email_to_admin, send_email_to_customer, replicate_monthly_routes, flash_message
from flask_cors import CORS
from collections import defaultdict
from flask_apscheduler import APScheduler