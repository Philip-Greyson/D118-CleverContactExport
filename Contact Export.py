"""Script to export parent/guardian emails for each student and export to csv file for upload to Clever.

https://github.com/Philip-Greyson/D118-CleverContactExport

Only includes parent/guardians that have custody of the student and have an email (not blank).
Uploads the resulting .csv file to Clever via SFTP.

Needs pysftp: pip install pysftp --upgrade
Needs oracledb: pip install oracledb --upgrade

See below for all the relevant tables in PS for retreiving contact information
https://ps.powerschool-docs.com/pssis-data-dictionary/latest/studentcontactassoc-ver12-0-0
https://ps.powerschool-docs.com/pssis-data-dictionary/latest/studentcontactdetail-ver12-0-0
https://ps.powerschool-docs.com/pssis-data-dictionary/latest/person-188-ver5-0-0
https://ps.powerschool-docs.com/pssis-data-dictionary/latest/personemailaddressassoc-ver12-0-0
https://ps.powerschool-docs.com/pssis-data-dictionary/latest/emailaddress-ver12-0-0
"""

# importing module
import datetime  # only needed for logging purposes
import os  # needed to get system variables which have the PS IP and password in them
from datetime import *

import oracledb  # needed to connect to the PowerSchool database (oracle database)
import pysftp  # used to connect to the Clever sftp site and upload the file

un = os.environ.get('POWERSCHOOL_READ_USER')  # username for read-only database user
pw = os.environ.get('POWERSCHOOL_DB_PASSWORD')  # the password for the database account
cs = os.environ.get('POWERSCHOOL_PROD_DB')  # the IP address, port, and database name to connect to

#set up sftp login info, stored as environment variables on system
sftpUN = os.environ.get('CLEVER_SFTP_USERNAME')
sftpPW = os.environ.get('CLEVER_SFTP_PASSWORD')
sftpHOST = os.environ.get('CLEVER_SFTP_ADDRESS')
cnopts = pysftp.CnOpts(knownhosts='known_hosts')  # connection options to use the known_hosts file for key validation

print(f"Username: {un} |Password: {pw} |Server: {cs}")  # debug so we can see where oracle is trying to connect to/with
print(f"SFTP Username: {sftpUN} |SFTP Password: {sftpPW} |SFTP Server: {sftpHOST}")  # debug so we can see where oracle is trying to connect to/with
badnames = ['use', 'teststudent', 'test student', 'testtt', 'testtest', 'karentest', 'tester']

# create the connecton to the database
with oracledb.connect(user=un, password=pw, dsn=cs) as con:
    with con.cursor() as cur:  # start an entry cursor
        with open('CleverContactsLog.txt', 'w') as log:
            with open('contacts.csv', 'w') as outputfile:  # open the output file
                startTime = datetime.now()
                startTime = startTime.strftime('%H:%M:%S')
                print(f'INFO: Execution started at {startTime}')
                print(f'INFO: Execution started at {startTime}', file=log)
                print(f'Connection established to PS database on version: {con.version}')
                print(f'Connection established to PS database on version: {con.version}', file=log)

                print("contact_id,student_id,first_name,last_name,type,relationship,phone,phone_type,email",file=outputfile)  # print out header row into output file
                cur.execute('SELECT student_number, first_name, last_name, dcid, id FROM students WHERE enroll_status = 0 ORDER BY student_number DESC')  # get the basic student info, only for active students
                studentRows = cur.fetchall()  # store the data from the query into the studentRows variable

                # go through each student entry from the results of the students query
                for student in studentRows:
                    try:  # separate each student entry into its own try/except so if a student throws an error it continues to the next
                        guardianEmail = ""  # reset all fields to blanks for each student to prevent run-over
                        contactFirstName = ""
                        contactLastName = ""
                        relationship = ""
                        phoneNumber = ""
                        phoneType = ""
                        studentfirstName = str(student[1])
                        studentlastName = str(student[2])
                        # print(student)  # debug

                        # check first and last name against array of bad names, only print if both come back not in it
                        if not studentfirstName.lower() in badnames and not studentlastName.lower() in badnames:
                            # want to take as int to avoid .0 trails. student_number is probably no longer needed
                            idNum = int(student[0])
                            # get the student dcid for use in further queries
                            stuDCID = str(student[3])
                            # get the internal student ID number, since clever wants that for some reason
                            stuID = str(student[4])
                            print(f'DBUG: Processing student {idNum} - {studentfirstName} {studentlastName}')
                            print(f'DBUG: Processing student {idNum} - {studentfirstName} {studentlastName}', file=log)
                            #start a query of the contact associations for the student, filtering to only entries that have custodial access
                            cur.execute('SELECT StudentContactAssoc.PersonID, StudentContactDetail.RelationshipTypeCodeSetID FROM StudentContactAssoc LEFT JOIN StudentContactDetail ON StudentContactAssoc.StudentContactAssocID = StudentContactDetail.StudentContactAssocID WHERE StudentContactDetail.IsCustodial = 1 AND StudentContactAssoc.StudentDCID = ' + stuDCID)
                            contactRows = cur.fetchall()
                            for contact in contactRows:  # go through each of the contacts that have custodial rights, now we will take their person id to get name and email
                                try:
                                    # print(contact)  # debug
                                    contactID = str(contact[0])
                                    relationshipCode = str(contact[1])
                                    # take the relationshiptypecodesetid and find the matching display name
                                    cur.execute('SELECT Code FROM CodeSet WHERE CodeSetID = ' + relationshipCode)
                                    relationshipResult = cur.fetchall()
                                    if relationshipResult:
                                        # store the relationship display name here or blank if no results
                                        relationship = str(relationshipResult[0][0]) if relationshipResult[0][0] else ""
                                    #print(relationship) #debug
                                    # take the contact id and find them in the person table
                                    cur.execute('SELECT FirstName, LastName FROM Person WHERE ID = ' + contactID)
                                    contactResult = cur.fetchall()
                                    if contactResult:
                                        contactFirstName = str(contactResult[0][0]) if contactResult[0][0] else ""
                                        contactLastName = str(contactResult[0][1]) if contactResult[0][1] else ""
                                    #print(firstName + " " + lastName) #debug
                                    # do a query on the email address table by passing the emailID found by querying the PersonEmailAddressAssoc table with the person ID
                                    cur.execute('SELECT EmailAddress.EmailAddress FROM PersonEmailAddressAssoc LEFT JOIN EmailAddress ON PersonEmailAddressAssoc.EmailAddressID = EmailAddress.EmailAddressID WHERE PersonEmailAddressAssoc.PersonID = ' + contactID)
                                    emailResult = cur.fetchall()
                                    if emailResult:
                                        guardianEmail = str(emailResult[0][0]) if emailResult[0][0] else ""
                                    #print(guardianEmail) #debug
                                    # do a similar query on the phone number table as above, but filter to PhoneNumberCodeSetID = 13 to only get mobile phones
                                    cur.execute('SELECT PhoneNumber.PhoneNumber FROM PersonPhoneNumberAssoc LEFT JOIN PhoneNumber ON PersonPhoneNumberAssoc.PhoneNumberID = PhoneNumber.PhoneNumberID WHERE PersonPhoneNumberAssoc.PhoneTypeCodeSetID = 13 AND PersonPhoneNumberAssoc.PersonID = ' + contactID)
                                    phoneResult = cur.fetchall()
                                    if phoneResult:
                                        phoneNumber = str(phoneResult[0][0]) if phoneResult[0][0] else ""
                                        if phoneNumber != "":
                                            phoneType = "Cell"
                                    # print(phoneNumber) #debug
                                    # if there is an actual email for the contact, we will add all their info to the output
                                    if guardianEmail != "" and guardianEmail != "N/A":
                                        print('"' + contactID + '",' + stuID + ',' + contactFirstName + ',' + contactLastName + ',Guardian,' + relationship + ',' + phoneNumber + ',' + phoneType + ',"' + guardianEmail + '"', file=outputfile)
                                except Exception as er:
                                    print(f'ERROR while accessing contact ID {contact[0]} for student {idNum}: {er}')
                                    print(f'ERROR while accessing contact ID {contact[0]} for student {idNum}: {er}', file=log)
                    except Exception as er:
                        print(f'ERROR while processing student {student[0]}: {er}')
                        print(f'ERROR while processing student {student[0]}: {er}', file=log)
            try:
                with pysftp.Connection(sftpHOST, username=sftpUN, password=sftpPW, cnopts=cnopts) as sftp:
                    print(f'INFO: SFTP connection established to {sftpHOST}')
                    print(f'INFO: SFTP connection established to {sftpHOST}', file=log)
                    # print(sftp.pwd) # debug, show what folder we connected to
                    # print(sftp.listdir())  # debug, show what other files/folders are in the current directory
                    sftp.chdir('./customcontacts')  # change to the extensionfields folder
                    # print(sftp.pwd) # debug, make sure out changedir worked
                    # print(sftp.listdir())
                    sftp.put('contacts.csv')  # upload the file onto the sftp server
                    print("INFO: Contacts file placed on remote server")
                    print("INFO: Contacts file placed on remote server", file=log)
            except Exception as er:
                print(f'ERROR during SFTP upload: {er}')
                print(f'ERROR during SFTP upload: {er}', file=log)

            endTime = datetime.now()
            endTime = endTime.strftime('%H:%M:%S')
            print(f'INFO: Execution ended at {endTime}')
            print(f'INFO: Execution ended at {endTime}', file=log)
