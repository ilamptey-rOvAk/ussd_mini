
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI()

class USSDRequest(BaseModel):
    USERID: str
    MSISDN: str
    USERDATA: str
    MSGTYPE: bool
    SESSIONID: str

NALO_USER_ID = "AIK12345"

DATABASE = Path(__file__).parent / "ussd.db"


# USSD menu options
feelings = {
    "1": "Feeling fine",
    "2": "Feeling sad",
    "3": "Feeling frisky"
}

reasons = {
    "1": "relationship issues",
    "2": "money problem",
    "3": "family issues"
}


# Connect to SQLite database
def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# Create the sessions table
def create_table():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            phone_number TEXT,
            feeling TEXT,
            reason TEXT,
            current_step TEXT
        )
    """)

    connection.commit()
    connection.close()


create_table()


# Welcome menu
def welcome_menu():
    return (
        "Welcome.\n"
        "How are you feeling today?\n"
        "1. Feeling fine\n"
        "2. Feeling sad\n"
        "3. Feeling frisky"
    )


# Reason menu
def reason_menu(feeling):
    return (
        f"You are {feeling} because:\n"
        "1. Relationship issues\n"
        "2. Money problem\n"
        "3. Family issues"
    )


# Prepare response for NALO
def nalo_response(user_id, msisdn, message, msgtype):
    return {
        "USERID": user_id,
        "MSISDN": msisdn,
        "MSG": message,
        "MSGTYPE": msgtype
    }


# Homepage
@app.get("/")
def home():
    return {
        "message": "USSD application is running"
    }


# USSD endpoint status
@app.get("/ussd/")
def ussd_status():
    return {
        "status": "ok",
        "endpoint": "/ussd/"
    }


# Main USSD endpoint

@app.post("/ussd/")
async def handle_ussd(data: USSDRequest):

    user_id = data.USERID
    msisdn = data.MSISDN
    user_input = data.USERDATA.strip()
    session_id = data.SESSIONID
    msgtype = data.MSGTYPE

    if user_id != NALO_USER_ID:
        raise HTTPException(
            status_code=400,
            detail="Invalid USERID"
        )

    # Start a new session
    if msgtype is True:

        connection = get_db()

        connection.execute("""
            INSERT OR REPLACE INTO sessions
            (session_id, phone_number, current_step)
            VALUES (?, ?, ?)
        """, (
            session_id,
            msisdn,
            "feeling"
        ))

        connection.commit()
        connection.close()

        return nalo_response(
            user_id,
            msisdn,
            welcome_menu(),
            True
        )

    # Continue an existing session
    connection = get_db()

    session = connection.execute("""
        SELECT * FROM sessions
        WHERE session_id = ?
    """, (session_id,)).fetchone()

    if session is None:
        connection.close()

        return nalo_response(
            user_id,
            msisdn,
            "Your session has expired. Please dial again.",
            False
        )

    # Step 1: Receive the user's feeling
    if session["current_step"] == "feeling":

        if user_input not in feelings:
            connection.close()

            return nalo_response(
                user_id,
                msisdn,
                "Invalid selection.\n" + welcome_menu(),
                True
            )

        selected_feeling = feelings[user_input]

        connection.execute("""
            UPDATE sessions
            SET feeling = ?, current_step = ?
            WHERE session_id = ?
        """, (
            selected_feeling,
            "reason",
            session_id
        ))

        connection.commit()
        connection.close()

        return nalo_response(
            user_id,
            msisdn,
            reason_menu(selected_feeling),
            True
        )

    # Step 2: Receive the user's reason
    elif session["current_step"] == "reason":

        if user_input not in reasons:
            selected_feeling = session["feeling"]

            connection.close()

            return nalo_response(
                user_id,
                msisdn,
                "Invalid selection.\n" + reason_menu(selected_feeling),
                True
            )

        selected_reason = reasons[user_input]

        connection.execute("""
            UPDATE sessions
            SET reason = ?, current_step = ?
            WHERE session_id = ?
        """, (
            selected_reason,
            "completed",
            session_id
        ))

        connection.commit()
        connection.close()

        final_message = (
            f"Sorry you are experiencing {selected_reason}. "
            "Hope things get better soon."
        )

        return nalo_response(
            user_id,
            msisdn,
            final_message,
            False
        )

    connection.close()

    return nalo_response(
        user_id,
        msisdn,
        "This session has ended. Please dial again.",
        False
    )
