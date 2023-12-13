
# D118-CleverContactExport

Gets the contact/guardian email and cell phone for each student, and exports it to a .csv file which is uploaded via SFTP to Clever.

## Overview

The script first does a query for all active students in PowerSchool. It then begins to go through each student one at a time, doing a further query for the student contacts who have custodial rights.
Then it takes each contact entry and retrieves the relevant parent information from a number of tables:

- The relationship type (mother, father, etc) by matching the StudentContactDetail.RelationshipTypeCodeSetID to the CodeSetID table.
- The contact's first and last name from the Person table
- The contact's email from EmailAddress by getting the PersonEmailAddressAssoc.EmailAddressID based on their contact PersonID
- The contact's cell phone number from PhoneNumber by getting the PersonPhoneNumberAssoc.PhoneNumberID based on their contact PersonID

If there is an email found for these contacts, it then takes all the information for that contact and exports it as a line in the output .csv file in the format that Clever expects for its contacts.csv. If there is no email, that contact is skipped.
Then a SFTP connection is established to the Clever server, and the .csv file is uploaded to the server.

## Requirements

The following Environment Variables must be set on the machine running the script:

- POWERSCHOOL_READ_USER
- POWERSCHOOL_DB_PASSWORD
- POWERSCHOOL_PROD_DB
- CLEVER_SFTP_USERNAME
- CLEVER_SFTP_PASSWORD
- CLEVER_SFTP_ADDRESS

These are fairly self explanatory, and just relate to the usernames, passwords, and host IP/URLs for PowerSchool and Clever. If you wish to directly edit the script and include these credentials, you can.

Additionally, the following Python libraries must be installed on the host machine (links to the installation guide):

- [Python-oracledb](https://python-oracledb.readthedocs.io/en/latest/user_guide/installation.html)
- [pysftp](https://pypi.org/project/pysftp/)

**As part of the pysftp connection to the Clever SFTP server, you must include the server host key in a file** with no extension named "known_hosts" in the same directory as the Python script. You can see [here](https://pysftp.readthedocs.io/en/release_0.2.9/cookbook.html#pysftp-cnopts) for details on how it is used, but the easiest way to include this I have found is to create an SSH connection from a linux machine using the login info and then find the key (the newest entry should be on the bottom) in ~/.ssh/known_hosts and copy and paste that into a new file named "known_hosts" in the script directory.

## Customization

This script should *"just work"* even for other districts outside of D118 as it uses standard PowerSchool tables and outputs to the format required by Clever, as long as the requirements above are met. However, there may be a few things you want to change depending on your use case:

- If you want all contacts to be exported not just those with custody, remove `WHERE StudentContactDetail.IsCustodial = 1` from the second overall SQL query (the main one to find student contacts).
  - You will then want to change the static "Guardian" contact type that is included in the final output, likely mapping it to different values based on contact type.
- We choose to only include cell phone numbers for the contacts. If you want to change that, you will need to remove `WHERE PersonPhoneNumberAssoc.PhoneTypeCodeSetID = 13` from the final query inside of the contact section.
  - You will also then need to get the phone number type code from that and map that using the CodeSet table into a string for export in the final output.
