"""
Relational implementation of basic resource metadata storage.
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, create_engine,\
        ForeignKey, Table, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref, sessionmaker

from taxus.data import Node, Locator, ContentDescriptor, Resource



