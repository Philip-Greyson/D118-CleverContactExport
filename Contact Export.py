# Program to export parent/guardian emails for each student. Only prints out if the contact has custody of them, and has an email
# Then takes the output and uploads it to the Clever SFTP server for their processing
# documentation for the tables used to get contacts and stuff
# https://docs.powerschool.com/PSDD/powerschool-tables/studentcontactassoc-ver12-0-0
# https://docs.powerschool.com/PSDD/powerschool-tables/studentcontactdetail-ver12-0-0
# https://docs.powerschool.com/PSDD/powerschool-tables/person-188-ver5-0-0
# https://docs.powerschool.com/PSDD/powerschool-tables/personemailaddressassoc-ver12-0-0
# https://docs.powerschool.com/PSDD/powerschool-tables/emailaddress-ver12-0-0

# importing module
import pysftp  # used to connect to the Clever sftp site and upload the file
import os  # needed to get system variables which have the PS IP and password in them
import oracledb # needed to connect to the PowerSchool database (oracle database)

un = 'PSNavigator'  # PSNavigator is read only, PS is read/write
pw = os.environ.get('POWERSCHOOL_DB_PASSWORD') # the password for the PSNavigator account
cs = os.environ.get('POWERSCHOOL_PROD_DB') # the IP address, port, and database name to connect to

#set up sftp login info, stored as environment variables on system
sftpUN = os.environ.get('CLEVER_SFTP_USERNAME')
sftpPW = os.environ.get('CLEVER_SFTP_PASSWORD')
sftpHOST = os.environ.get('CLEVER_SFTP_ADDRESS')
cnopts = pysftp.CnOpts(knownhosts='known_hosts') #connection options to use the known_hosts file for key validation

print("Username: " + str(un) + " |Password: " + str(pw) + " |Server: " + str(cs))
print("SFTP Username: " + str(sftpUN) + " |SFTP Password: " + str(sftpPW) + " |SFTP Server: " + str(sftpHOST)) #debug so we can see what sftp info is being used
badnames = ['USE', 'TESTSTUDENT', 'TEST STUDENT', 'TESTTT', 'TESTTEST']

# create the connecton to the database
with oracledb.connect(user=un, password=pw, dsn=cs) as con:
    with con.cursor() as cur:  # start an entry cursor
        with open('contacts.csv', 'w') as outputfile:  # open the output file
            print("Connection established: " + con.version)
            print("contact_id,student_id,first_name,last_name,type,relationship,phone,phone_type,email",file=outputfile)  # print out header row
            cur.execute('SELECT student_number, first_name, last_name, dcid FROM students WHERE enroll_status = 0 ORDER BY student_number DESC')
            studentRows = cur.fetchall()  # store the data from the query into the rows variable

            # go through each entry (which is a tuple) in rows. Each entrytuple is a single students's data
            for student in studentRows:
                try:  # separate each student entry into its own try/except so if a student throws an error it continues to the next
                    guardianEmail = ""  # reset all fields to blanks for each student to prevent run-over
                    firstName = ""
                    lastName = ""
                    relationship = ""
                    # print(student)  # debug
                    # convert the tuple which is immutable to a list which we can edit. Now entry[] is an array/list of the student data
                    studentEntry = list(student)
                    # check first and last name against array of bad names, only print if both come back not in it
                    if not str(studentEntry[1]) in badnames and not str(studentEntry[2]) in badnames:
                        # want to take as int to avoid .0 trails
                        idNum = int(studentEntry[0])
                        # get the student dcid for use in further queries
                        stuDCID = str(studentEntry[3])
                        #start a query of the contact associations for the student, filtering to only entries that have custodial access
                        cur.execute('SELECT StudentContactAssoc.PersonID, StudentContactDetail.RelationshipTypeCodeSetID FROM StudentContactAssoc LEFT JOIN StudentContactDetail ON StudentContactAssoc.StudentContactAssocID = StudentContactDetail.StudentContactAssocID WHERE StudentContactDetail.IsCustodial = 1 AND StudentContactAssoc.StudentDCID = ' + stuDCID)
                        contactRows = cur.fetchall()
                        for contact in contactRows:  # go through each of the contacts that have custodial rights, now we will take their person id to get name and email
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
                                firstName = str(contactResult[0][0]) if contactResult[0][0] else ""
                                lastName = str(contactResult[0][1]) if contactResult[0][1] else ""
                            #print(firstName + " " + lastName) #debug
                            cur.execute('SELECT EmailAddress.EmailAddress FROM PersonEmailAddressAssoc LEFT JOIN EmailAddress ON PersonEmailAddressAssoc.EmailAddressID = EmailAddress.EmailAddressID WHERE PersonEmailAddressAssoc.PersonID = ' + contactID)
                            emailResult = cur.fetchall()
                            if emailResult:
                                guardianEmail = str(emailResult[0][0]) if emailResult[0][0] else ""
                            #print(guardianEmail) #debug
                            # if there is an actual email for the contact, we will add all their info to the output
                            if guardianEmail != "" and guardianEmail != "N/A":
                                print('"' + contactID + '",' + str(idNum) + ',' + firstName + ',' + lastName + ',Guardian,'+relationship+',,,"'+guardianEmail+'"', file=outputfile)
                except Exception as er:
                    print('Unknown Error: '+str(er))

with pysftp.Connection(sftpHOST, username=sftpUN, password=sftpPW, cnopts=cnopts) as sftp:
    print('SFTP connection established')
    # print(sftp.pwd) # debug, show what folder we connected to
    # print(sftp.listdir())  # debug, show what other files/folders are in the current directory
    sftp.chdir('./customcontacts')  # change to the extensionfields folder
    # print(sftp.pwd) # debug, make sure out changedir worked
    # print(sftp.listdir())
    sftp.put('contacts.csv')  # upload the file onto the sftp server
    print("Contacts file placed on remote server")
