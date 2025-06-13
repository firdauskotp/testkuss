
import gridfs
from  backend.col import db  # Assuming db is defined in the same package
from flask_mail import Mail
import os
mail = Mail()
fs = gridfs.GridFS(db)
