


set sql_safe_updates=0;
set foreign_key_checks=0;
UPDATE c_configuration SET enabled = 0 WHERE name = 'amazon-S3';
UPDATE c_external_service_properties set value = 'demo' where name = 's3_access_key';
UPDATE c_external_service_properties set value = 'demo' where name = 's3_bucket_name';
UPDATE c_external_service_properties set value = 'demo' where name = 's3_secret_key';
truncate external_services_config;
UPDATE c_external_service_properties set value = 'demo' where name = 'username';
UPDATE c_external_service_properties set value = 'demo' where name = 'password';
UPDATE communication_configuration SET activate=0;
UPDATE communication_sms_job_mapping SET is_active=0;
truncate  c_external_service_properties;
truncate  m_payment_gateway_vendors;
truncate communication_sms_event_mapping ;
truncate communication_sms_job_mapping ;
truncate communication_channel ;
truncate communication_configuration ;
truncate m_hook_configuration;
truncate m_hook_schema;
truncate m_organisation_details ;
truncate m_e_nach_external_service;
update job  set is_active =0 where name='enach presentation';
update m_appuser 
set email='thedarji.creations@gmail.com';
set foreign_key_checks=1;


UPDATE m_client
SET
    firstname = (SELECT name FROM (SELECT "Priya" AS name UNION ALL
                                    SELECT "Rahul" UNION ALL
                                    SELECT "Anika" UNION ALL
                                    SELECT "Rohit" UNION ALL
                                    SELECT "Aisha" UNION ALL
                                    SELECT "Arjun" UNION ALL
                                    SELECT "Neha" UNION ALL
                                    SELECT "Raj" UNION ALL
                                    SELECT "Shreya" UNION ALL
                                    SELECT "Vishal" UNION ALL
                                    SELECT "Aarav" UNION ALL
                                    SELECT "Pooja" UNION ALL
                                    SELECT "Vikram" UNION ALL
                                    SELECT "Meera" UNION ALL
                                    SELECT "Sanjay" UNION ALL
                                    SELECT "Riya" UNION ALL
                                    SELECT "Sameer" UNION ALL
                                    SELECT "Nisha" UNION ALL
                                    SELECT "Aditya" UNION ALL
                                    SELECT "Komal" UNION ALL
                                    SELECT "Siddharth" UNION ALL
                                    SELECT "Kavita" UNION ALL
                                    SELECT "Akash" UNION ALL
                                    SELECT "Ritu" UNION ALL
                                    SELECT "Prateek" UNION ALL
                                    SELECT "Divya" UNION ALL
                                    SELECT "Abhishek" UNION ALL
                                    SELECT "Maya" UNION ALL
                                    SELECT "Karan" UNION ALL
                                    SELECT "Sneha" UNION ALL
                                    SELECT "Yash" UNION ALL
                                    SELECT "Nidhi" UNION ALL
                                    SELECT "Suresh" UNION ALL
                                    SELECT "Manisha" UNION ALL
                                    SELECT "Amit" UNION ALL
                                    SELECT "Swati" UNION ALL
                                    SELECT "Ravi" UNION ALL
                                    SELECT "Mona" UNION ALL
                                    SELECT "Arun" UNION ALL
                                    SELECT "Radha" UNION ALL
                                    SELECT "Hitesh" UNION ALL
                                    SELECT "Shilpa" UNION ALL
                                    SELECT "Rajesh" UNION ALL
                                    SELECT "Aarti" UNION ALL
                                    SELECT "Sumit" UNION ALL
                                    SELECT "Sakshi" UNION ALL
                                    SELECT "Sunil" UNION ALL
                                    SELECT "Anjali" UNION ALL
                                    SELECT "Rakesh" UNION ALL
                                    SELECT "Simran") AS firstnames ORDER BY RAND() LIMIT 1),
    middlename = (SELECT name FROM (SELECT "Kumar" AS name UNION ALL
                                    SELECT "Singh" UNION ALL
                                    SELECT "Devi" UNION ALL
                                    SELECT "Raj" UNION ALL
                                    SELECT "Kumari" UNION ALL
                                    SELECT "Patel" UNION ALL
                                    SELECT "Kaur" UNION ALL
                                    SELECT "Chandra" UNION ALL
                                    SELECT "Sharma" UNION ALL
                                    SELECT "Gupta") AS middlenames ORDER BY RAND() LIMIT 1),
    lastname = (SELECT name FROM (SELECT "Patel" AS name UNION ALL
                                   SELECT "Sharma" UNION ALL
                                   SELECT "Gupta" UNION ALL
                                   SELECT "Singh" UNION ALL
                                   SELECT "Kumar" UNION ALL
                                   SELECT "Yadav" UNION ALL
                                   SELECT "Jain" UNION ALL
                                   SELECT "Gupta" UNION ALL
                                   SELECT "Rao" UNION ALL
                                   SELECT "Reddy" UNION ALL
                                   SELECT "Choudhury" UNION ALL
                                   SELECT "Pandey" UNION ALL
                                   SELECT "Agarwal" UNION ALL
                                   SELECT "Verma" UNION ALL
                                   SELECT "Dixit" UNION ALL
                                   SELECT "Mishra" UNION ALL
                                   SELECT "Mehta" UNION ALL
                                   SELECT "Shah" UNION ALL
                                   SELECT "Khan" UNION ALL
                                   SELECT "Das" UNION ALL
                                   SELECT "Rajput" UNION ALL
                                   SELECT "Biswas" UNION ALL
                                   SELECT "Chatterjee" UNION ALL
                                   SELECT "Malik" UNION ALL
                                   SELECT "Ahmed" UNION ALL
                                   SELECT "Malhotra" UNION ALL
                                   SELECT "Kapoor" UNION ALL
                                   SELECT "Sinha" UNION ALL
                                   SELECT "Bhat" UNION ALL
                                   SELECT "Nair" UNION ALL
                                   SELECT "Iyer" UNION ALL
                                   SELECT "Menon" UNION ALL
                                   SELECT "Pillai" UNION ALL
                                   SELECT "Menon" UNION ALL
                                   SELECT "George" UNION ALL
                                   SELECT "Thomas" UNION ALL
                                   SELECT "Kamble" UNION ALL
                                   SELECT "Pawar" UNION ALL
                                   SELECT "Jadhav" UNION ALL
                                   SELECT "Chavan" UNION ALL
                                   SELECT "Deshmukh" UNION ALL
                                   SELECT "Dutta" UNION ALL
                                   SELECT "Barua" UNION ALL
                                   SELECT "Goswami" UNION ALL
                                   SELECT "Bose" UNION ALL
                                   SELECT "Sen" UNION ALL
                                   SELECT "Banerjee" UNION ALL
                                   SELECT "Roy" UNION ALL
                                   SELECT "Thakur") AS lastnames ORDER BY RAND() LIMIT 1),
    display_name = CONCAT(
        (SELECT name FROM (SELECT "Priya" AS name UNION ALL
                            SELECT "Rahul" UNION ALL
                            SELECT "Anika" UNION ALL
                            SELECT "Rohit" UNION ALL
                            SELECT "Aisha" UNION ALL
                            SELECT "Arjun" UNION ALL
                            SELECT "Neha" UNION ALL
                            SELECT "Raj" UNION ALL
                            SELECT "Shreya" UNION ALL
                            SELECT "Vishal" UNION ALL
                            SELECT "Aarav" UNION ALL
                            SELECT "Pooja" UNION ALL
                            SELECT "Vikram" UNION ALL
                            SELECT "Meera" UNION ALL
                            SELECT "Sanjay" UNION ALL
                            SELECT "Riya" UNION ALL
                            SELECT "Sameer" UNION ALL
                            SELECT "Nisha" UNION ALL
                            SELECT "Aditya" UNION ALL
                            SELECT "Komal" UNION ALL
                            SELECT "Siddharth" UNION ALL
                            SELECT "Kavita" UNION ALL
                            SELECT "Akash" UNION ALL
                            SELECT "Ritu" UNION ALL
                            SELECT "Prateek" UNION ALL
                            SELECT "Divya" UNION ALL
                            SELECT "Abhishek" UNION ALL
                            SELECT "Maya" UNION ALL
                            SELECT "Karan" UNION ALL
                            SELECT "Sneha" UNION ALL
                            SELECT "Yash" UNION ALL
                            SELECT "Nidhi" UNION ALL
                            SELECT "Suresh" UNION ALL
                            SELECT "Manisha" UNION ALL
                            SELECT "Amit" UNION ALL
                            SELECT "Swati" UNION ALL
                            SELECT "Ravi" UNION ALL
                            SELECT "Mona" UNION ALL
                            SELECT "Arun" UNION ALL
                            SELECT "Radha" UNION ALL
                            SELECT "Hitesh" UNION ALL
                            SELECT "Shilpa" UNION ALL
                            SELECT "Rajesh" UNION ALL
                            SELECT "Aarti" UNION ALL
                            SELECT "Sumit" UNION ALL
                            SELECT "Sakshi" UNION ALL
                            SELECT "Sunil" UNION ALL
                            SELECT "Anjali" UNION ALL
                            SELECT "Rakesh" UNION ALL
                            SELECT "Simran") AS firstnames ORDER BY RAND() LIMIT 1),
        ' ',
        (SELECT name FROM (SELECT "Kumar" AS name UNION ALL
                            SELECT "Singh" UNION ALL
                            SELECT "Devi" UNION ALL
                            SELECT "Raj" UNION ALL
                            SELECT "Kumari" UNION ALL
                            SELECT "Patel" UNION ALL
                            SELECT "Kaur" UNION ALL
                            SELECT "Chandra" UNION ALL
                            SELECT "Sharma" UNION ALL
                            SELECT "Gupta") AS middlenames ORDER BY RAND() LIMIT 1),
        ' ',
        (SELECT name FROM (SELECT "Patel" AS name UNION ALL
                            SELECT "Sharma" UNION ALL
                            SELECT "Gupta" UNION ALL
                            SELECT "Singh" UNION ALL
                            SELECT "Kumar" UNION ALL
                            SELECT "Yadav" UNION ALL
                            SELECT "Jain" UNION ALL
                            SELECT "Gupta" UNION ALL
                            SELECT "Rao" UNION ALL
                            SELECT "Reddy" UNION ALL
                            SELECT "Choudhury" UNION ALL
                            SELECT "Pandey" UNION ALL
                            SELECT "Agarwal" UNION ALL
                            SELECT "Verma" UNION ALL
                            SELECT "Dixit" UNION ALL
                            SELECT "Mishra" UNION ALL
                            SELECT "Mehta" UNION ALL
                            SELECT "Shah" UNION ALL
                            SELECT "Khan" UNION ALL
                            SELECT "Das" UNION ALL
                            SELECT "Rajput" UNION ALL
                            SELECT "Biswas" UNION ALL
                            SELECT "Chatterjee" UNION ALL
                            SELECT "Malik" UNION ALL
                            SELECT "Ahmed" UNION ALL
                            SELECT "Malhotra" UNION ALL
                            SELECT "Kapoor" UNION ALL
                            SELECT "Sinha" UNION ALL
                            SELECT "Bhat" UNION ALL
                            SELECT "Nair" UNION ALL
                            SELECT "Iyer" UNION ALL
                            SELECT "Menon" UNION ALL
                            SELECT "Pillai" UNION ALL
                            SELECT "Menon" UNION ALL
                            SELECT "George" UNION ALL
                            SELECT "Thomas" UNION ALL
                            SELECT "Kamble" UNION ALL
                            SELECT "Pawar" UNION ALL
                            SELECT "Jadhav" UNION ALL
                            SELECT "Chavan" UNION ALL
                            SELECT "Deshmukh" UNION ALL
                            SELECT "Dutta" UNION ALL
                            SELECT "Barua" UNION ALL
                            SELECT "Goswami" UNION ALL
                            SELECT "Bose" UNION ALL
                            SELECT "Sen" UNION ALL
                            SELECT "Banerjee" UNION ALL
                            SELECT "Roy" UNION ALL
                            SELECT "Thakur") AS lastnames ORDER BY RAND() LIMIT 1)
    );
   
 
  
 update  m_client set display_name=CONCAT(ifnull(firstname,''),' ', ifnull(middlename,''),' ', ifnull(lastname,'')  );
  
  UPDATE m_client 
   set mobile_no = CONCAT(SUBSTRING(mobile_no, 6 ),SUBSTRING(mobile_no, 1, 5 ));
  
  UPDATE m_client set email_address='thedarji.creations@gmail.com';
  
    UPDATE m_appuser  
   set mobile_no = CONCAT(SUBSTRING(mobile_no, 6 ),SUBSTRING(mobile_no, 1, 5 ));

UPDATE m_enquiry
SET
    fullname = CONCAT(
        (SELECT name FROM (SELECT "Priya" AS name UNION ALL
                            SELECT "Rahul" UNION ALL
                            SELECT "Anika" UNION ALL
                            SELECT "Rohit" UNION ALL
                            SELECT "Aisha" UNION ALL
                            SELECT "Arjun" UNION ALL
                            SELECT "Neha" UNION ALL
                            SELECT "Raj" UNION ALL
                            SELECT "Shreya" UNION ALL
                            SELECT "Vishal" UNION ALL
                            SELECT "Aarav" UNION ALL
                            SELECT "Pooja" UNION ALL
                            SELECT "Vikram" UNION ALL
                            SELECT "Meera" UNION ALL
                            SELECT "Sanjay" UNION ALL
                            SELECT "Riya" UNION ALL
                            SELECT "Sameer" UNION ALL
                            SELECT "Nisha" UNION ALL
                            SELECT "Aditya" UNION ALL
                            SELECT "Komal" UNION ALL
                            SELECT "Siddharth" UNION ALL
                            SELECT "Kavita" UNION ALL
                            SELECT "Akash" UNION ALL
                            SELECT "Ritu" UNION ALL
                            SELECT "Prateek" UNION ALL
                            SELECT "Divya" UNION ALL
                            SELECT "Abhishek" UNION ALL
                            SELECT "Maya" UNION ALL
                            SELECT "Karan" UNION ALL
                            SELECT "Sneha" UNION ALL
                            SELECT "Yash" UNION ALL
                            SELECT "Nidhi" UNION ALL
                            SELECT "Suresh" UNION ALL
                            SELECT "Manisha" UNION ALL
                            SELECT "Amit" UNION ALL
                            SELECT "Swati" UNION ALL
                            SELECT "Ravi" UNION ALL
                            SELECT "Mona" UNION ALL
                            SELECT "Arun" UNION ALL
                            SELECT "Radha" UNION ALL
                            SELECT "Hitesh" UNION ALL
                            SELECT "Shilpa" UNION ALL
                            SELECT "Rajesh" UNION ALL
                            SELECT "Aarti" UNION ALL
                            SELECT "Sumit" UNION ALL
                            SELECT "Sakshi" UNION ALL
                            SELECT "Sunil" UNION ALL
                            SELECT "Anjali" UNION ALL
                            SELECT "Rakesh" UNION ALL
                            SELECT "Simran") AS firstnames ORDER BY RAND() LIMIT 1),
        ' ',
        (SELECT name FROM (SELECT "Kumar" AS name UNION ALL
                            SELECT "Singh" UNION ALL
                            SELECT "Devi" UNION ALL
                            SELECT "Raj" UNION ALL
                            SELECT "Kumari" UNION ALL
                            SELECT "Patel" UNION ALL
                            SELECT "Kaur" UNION ALL
                            SELECT "Chandra" UNION ALL
                            SELECT "Sharma" UNION ALL
                            SELECT "Gupta") AS middlenames ORDER BY RAND() LIMIT 1),
        ' ',
        (SELECT name FROM (SELECT "Patel" AS name UNION ALL
                            SELECT "Sharma" UNION ALL
                            SELECT "Gupta" UNION ALL
                            SELECT "Singh" UNION ALL
                            SELECT "Kumar" UNION ALL
                            SELECT "Yadav" UNION ALL
                            SELECT "Jain" UNION ALL
                            SELECT "Gupta" UNION ALL
                            SELECT "Rao" UNION ALL
                            SELECT "Reddy" UNION ALL
                            SELECT "Choudhury" UNION ALL
                            SELECT "Pandey" UNION ALL
                            SELECT "Agarwal" UNION ALL
                            SELECT "Verma" UNION ALL
                            SELECT "Dixit" UNION ALL
                            SELECT "Mishra" UNION ALL
                            SELECT "Mehta" UNION ALL
                            SELECT "Shah" UNION ALL
                            SELECT "Khan" UNION ALL
                            SELECT "Das" UNION ALL
                            SELECT "Rajput" UNION ALL
                            SELECT "Biswas" UNION ALL
                            SELECT "Chatterjee" UNION ALL
                            SELECT "Malik" UNION ALL
                            SELECT "Ahmed" UNION ALL
                            SELECT "Malhotra" UNION ALL
                            SELECT "Kapoor" UNION ALL
                            SELECT "Sinha" UNION ALL
                            SELECT "Bhat" UNION ALL
                            SELECT "Nair" UNION ALL
                            SELECT "Iyer" UNION ALL
                            SELECT "Menon" UNION ALL
                            SELECT "Pillai" UNION ALL
                            SELECT "Menon" UNION ALL
                            SELECT "George" UNION ALL
                            SELECT "Thomas" UNION ALL
                            SELECT "Kamble" UNION ALL
                            SELECT "Pawar" UNION ALL
                            SELECT "Jadhav" UNION ALL
                            SELECT "Chavan" UNION ALL
                            SELECT "Deshmukh" UNION ALL
                            SELECT "Dutta" UNION ALL
                            SELECT "Barua" UNION ALL
                            SELECT "Goswami" UNION ALL
                            SELECT "Bose" UNION ALL
                            SELECT "Sen" UNION ALL
                            SELECT "Banerjee" UNION ALL
                            SELECT "Roy" UNION ALL
                            SELECT "Thakur") AS lastnames ORDER BY RAND() LIMIT 1)
    );
   -- mobile_no = REPLACE (mobile_no,SUBSTRING(mobile_no,2,4),"0000");

UPDATE m_family_members
SET
    firstname = (SELECT name FROM (SELECT "Priya" AS name UNION ALL
                                    SELECT "Rahul" UNION ALL
                                    SELECT "Anika" UNION ALL
                                    SELECT "Rohit" UNION ALL
                                    SELECT "Aisha" UNION ALL
                                    SELECT "Arjun" UNION ALL
                                    SELECT "Neha" UNION ALL
                                    SELECT "Raj" UNION ALL
                                    SELECT "Shreya" UNION ALL
                                    SELECT "Vishal" UNION ALL
                                    SELECT "Aarav" UNION ALL
                                    SELECT "Pooja" UNION ALL
                                    SELECT "Vikram" UNION ALL
                                    SELECT "Meera" UNION ALL
                                    SELECT "Sanjay" UNION ALL
                                    SELECT "Riya" UNION ALL
                                    SELECT "Sameer" UNION ALL
                                    SELECT "Nisha" UNION ALL
                                    SELECT "Aditya" UNION ALL
                                    SELECT "Komal" UNION ALL
                                    SELECT "Siddharth" UNION ALL
                                    SELECT "Kavita" UNION ALL
                                    SELECT "Akash" UNION ALL
                                    SELECT "Ritu" UNION ALL
                                    SELECT "Prateek" UNION ALL
                                    SELECT "Divya" UNION ALL
                                    SELECT "Abhishek" UNION ALL
                                    SELECT "Maya" UNION ALL
                                    SELECT "Karan" UNION ALL
                                    SELECT "Sneha" UNION ALL
                                    SELECT "Yash" UNION ALL
                                    SELECT "Nidhi" UNION ALL
                                    SELECT "Suresh" UNION ALL
                                    SELECT "Manisha" UNION ALL
                                    SELECT "Amit" UNION ALL
                                    SELECT "Swati" UNION ALL
                                    SELECT "Ravi" UNION ALL
                                    SELECT "Mona" UNION ALL
                                    SELECT "Arun" UNION ALL
                                    SELECT "Radha" UNION ALL
                                    SELECT "Hitesh" UNION ALL
                                    SELECT "Shilpa" UNION ALL
                                    SELECT "Rajesh" UNION ALL
                                    SELECT "Aarti" UNION ALL
                                    SELECT "Sumit" UNION ALL
                                    SELECT "Sakshi" UNION ALL
                                    SELECT "Sunil" UNION ALL
                                    SELECT "Anjali" UNION ALL
                                    SELECT "Rakesh" UNION ALL
                                    SELECT "Simran") AS firstnames ORDER BY RAND() LIMIT 1),
    middlename = (SELECT name FROM (SELECT "Kumar" AS name UNION ALL
                                    SELECT "Singh" UNION ALL
                                    SELECT "Devi" UNION ALL
                                    SELECT "Raj" UNION ALL
                                    SELECT "Kumari" UNION ALL
                                    SELECT "Patel" UNION ALL
                                    SELECT "Kaur" UNION ALL
                                    SELECT "Chandra" UNION ALL
                                    SELECT "Sharma" UNION ALL
                                    SELECT "Gupta") AS middlenames ORDER BY RAND() LIMIT 1),
    lastname = (SELECT name FROM (SELECT "Patel" AS name UNION ALL
                                   SELECT "Sharma" UNION ALL
                                   SELECT "Gupta" UNION ALL
                                   SELECT "Singh" UNION ALL
                                   SELECT "Kumar" UNION ALL
                                   SELECT "Yadav" UNION ALL
                                   SELECT "Jain" UNION ALL
                                   SELECT "Gupta" UNION ALL
                                   SELECT "Rao" UNION ALL
                                   SELECT "Reddy" UNION ALL
                                   SELECT "Choudhury" UNION ALL
                                   SELECT "Pandey" UNION ALL
                                   SELECT "Agarwal" UNION ALL
                                   SELECT "Verma" UNION ALL
                                   SELECT "Dixit" UNION ALL
                                   SELECT "Mishra" UNION ALL
                                   SELECT "Mehta" UNION ALL
                                   SELECT "Shah" UNION ALL
                                   SELECT "Khan" UNION ALL
                                   SELECT "Das" UNION ALL
                                   SELECT "Rajput" UNION ALL
                                   SELECT "Biswas" UNION ALL
                                   SELECT "Chatterjee" UNION ALL
                                   SELECT "Malik" UNION ALL
                                   SELECT "Ahmed" UNION ALL
                                   SELECT "Malhotra" UNION ALL
                                   SELECT "Kapoor" UNION ALL
                                   SELECT "Sinha" UNION ALL
                                   SELECT "Bhat" UNION ALL
                                   SELECT "Nair" UNION ALL
                                   SELECT "Iyer" UNION ALL
                                   SELECT "Menon" UNION ALL
                                   SELECT "Pillai" UNION ALL
                                   SELECT "Menon" UNION ALL
                                   SELECT "George" UNION ALL
                                   SELECT "Thomas" UNION ALL
                                   SELECT "Kamble" UNION ALL
                                   SELECT "Pawar" UNION ALL
                                   SELECT "Jadhav" UNION ALL
                                   SELECT "Chavan" UNION ALL
                                   SELECT "Deshmukh" UNION ALL
                                   SELECT "Dutta" UNION ALL
                                   SELECT "Barua" UNION ALL
                                   SELECT "Goswami" UNION ALL
                                   SELECT "Bose" UNION ALL
                                   SELECT "Sen" UNION ALL
                                   SELECT "Banerjee" UNION ALL
                                   SELECT "Roy" UNION ALL
                                   SELECT "Thakur") AS lastnames ORDER BY RAND() LIMIT 1),
    mobile_number = null;


UPDATE m_client_identifier
SET document_key = LPAD(CONV(FLOOR(RAND() * 36*36*36*36*36), 10, 36), 5, '0');

UPDATE m_enquiry_identifier
SET document_key = LPAD(CONV(FLOOR(RAND() * 36*36*36*36*36), 10, 36), 5, '0');

UPDATE m_kyc_entity
SET document_key = LPAD(CONV(FLOOR(RAND() * 36*36*36*36*36), 10, 36), 5, '0');

UPDATE g_sales_officer
SET
    firstname = (SELECT name FROM (SELECT "Priya" AS name UNION ALL
                                    SELECT "Rahul" UNION ALL
                                    SELECT "Anika" UNION ALL
                                    SELECT "Rohit" UNION ALL
                                    SELECT "Aisha" UNION ALL
                                    SELECT "Arjun" UNION ALL
                                    SELECT "Neha" UNION ALL
                                    SELECT "Raj" UNION ALL
                                    SELECT "Shreya" UNION ALL
                                    SELECT "Vishal" UNION ALL
                                    SELECT "Aarav" UNION ALL
                                    SELECT "Pooja" UNION ALL
                                    SELECT "Vikram" UNION ALL
                                    SELECT "Meera" UNION ALL
                                    SELECT "Sanjay" UNION ALL
                                    SELECT "Riya" UNION ALL
                                    SELECT "Sameer" UNION ALL
                                    SELECT "Nisha" UNION ALL
                                    SELECT "Aditya" UNION ALL
                                    SELECT "Komal" UNION ALL
                                    SELECT "Siddharth" UNION ALL
                                    SELECT "Kavita" UNION ALL
                                    SELECT "Akash" UNION ALL
                                    SELECT "Ritu" UNION ALL
                                    SELECT "Prateek" UNION ALL
                                    SELECT "Divya" UNION ALL
                                    SELECT "Abhishek" UNION ALL
                                    SELECT "Maya" UNION ALL
                                    SELECT "Karan" UNION ALL
                                    SELECT "Sneha" UNION ALL
                                    SELECT "Yash" UNION ALL
                                    SELECT "Nidhi" UNION ALL
                                    SELECT "Suresh" UNION ALL
                                    SELECT "Manisha" UNION ALL
                                    SELECT "Amit" UNION ALL
                                    SELECT "Swati" UNION ALL
                                    SELECT "Ravi" UNION ALL
                                    SELECT "Mona" UNION ALL
                                    SELECT "Arun" UNION ALL
                                    SELECT "Radha" UNION ALL
                                    SELECT "Hitesh" UNION ALL
                                    SELECT "Shilpa" UNION ALL
                                    SELECT "Rajesh" UNION ALL
                                    SELECT "Aarti" UNION ALL
                                    SELECT "Sumit" UNION ALL
                                    SELECT "Sakshi" UNION ALL
                                    SELECT "Sunil" UNION ALL
                                    SELECT "Anjali" UNION ALL
                                    SELECT "Rakesh" UNION ALL
                                    SELECT "Simran") AS firstnames ORDER BY RAND() LIMIT 1),
    lastname = (SELECT name FROM (SELECT "Patel" AS name UNION ALL
                                   SELECT "Sharma" UNION ALL
                                   SELECT "Gupta" UNION ALL
                                   SELECT "Singh" UNION ALL
                                   SELECT "Kumar" UNION ALL
                                   SELECT "Yadav" UNION ALL
                                   SELECT "Jain" UNION ALL
                                   SELECT "Gupta" UNION ALL
                                   SELECT "Rao" UNION ALL
                                   SELECT "Reddy" UNION ALL
                                   SELECT "Choudhury" UNION ALL
                                   SELECT "Pandey" UNION ALL
                                   SELECT "Agarwal" UNION ALL
                                   SELECT "Verma" UNION ALL
                                   SELECT "Dixit" UNION ALL
                                   SELECT "Mishra" UNION ALL
                                   SELECT "Mehta" UNION ALL
                                   SELECT "Shah" UNION ALL
                                   SELECT "Khan" UNION ALL
                                   SELECT "Das" UNION ALL
                                   SELECT "Rajput" UNION ALL
                                   SELECT "Biswas" UNION ALL
                                   SELECT "Chatterjee" UNION ALL
                                   SELECT "Malik" UNION ALL
                                   SELECT "Ahmed" UNION ALL
                                   SELECT "Malhotra" UNION ALL
                                   SELECT "Kapoor" UNION ALL
                                   SELECT "Sinha" UNION ALL
                                   SELECT "Bhat" UNION ALL
                                   SELECT "Nair" UNION ALL
                                   SELECT "Iyer" UNION ALL
                                   SELECT "Menon" UNION ALL
                                   SELECT "Pillai" UNION ALL
                                   SELECT "Menon" UNION ALL
                                   SELECT "George" UNION ALL
                                   SELECT "Thomas" UNION ALL
                                   SELECT "Kamble" UNION ALL
                                   SELECT "Pawar" UNION ALL
                                   SELECT "Jadhav" UNION ALL
                                   SELECT "Chavan" UNION ALL
                                   SELECT "Deshmukh" UNION ALL
                                   SELECT "Dutta" UNION ALL
                                   SELECT "Barua" UNION ALL
                                   SELECT "Goswami" UNION ALL
                                   SELECT "Bose" UNION ALL
                                   SELECT "Sen" UNION ALL
                                   SELECT "Banerjee" UNION ALL
                                   SELECT "Roy" UNION ALL
                                   SELECT "Thakur") AS lastnames ORDER BY RAND() LIMIT 1),
    display_name = CONCAT(
        (SELECT name FROM (SELECT "Priya" AS name UNION ALL
                            SELECT "Rahul" UNION ALL
                            SELECT "Anika" UNION ALL
                            SELECT "Rohit" UNION ALL
                            SELECT "Aisha" UNION ALL
                            SELECT "Arjun" UNION ALL
                            SELECT "Neha" UNION ALL
                            SELECT "Raj" UNION ALL
                            SELECT "Shreya" UNION ALL
                            SELECT "Vishal" UNION ALL
                            SELECT "Aarav" UNION ALL
                            SELECT "Pooja" UNION ALL
                            SELECT "Vikram" UNION ALL
                            SELECT "Meera" UNION ALL
                            SELECT "Sanjay" UNION ALL
                            SELECT "Riya" UNION ALL
                            SELECT "Sameer" UNION ALL
                            SELECT "Nisha" UNION ALL
                            SELECT "Aditya" UNION ALL
                            SELECT "Komal" UNION ALL
                            SELECT "Siddharth" UNION ALL
                            SELECT "Kavita" UNION ALL
                            SELECT "Akash" UNION ALL
                            SELECT "Ritu" UNION ALL
                            SELECT "Prateek" UNION ALL
                            SELECT "Divya" UNION ALL
                            SELECT "Abhishek" UNION ALL
                            SELECT "Maya" UNION ALL
                            SELECT "Karan" UNION ALL
                            SELECT "Sneha" UNION ALL
                            SELECT "Yash" UNION ALL
                            SELECT "Nidhi" UNION ALL
                            SELECT "Suresh" UNION ALL
                            SELECT "Manisha" UNION ALL
                            SELECT "Amit" UNION ALL
                            SELECT "Swati" UNION ALL
                            SELECT "Ravi" UNION ALL
                            SELECT "Mona" UNION ALL
                            SELECT "Arun" UNION ALL
                            SELECT "Radha" UNION ALL
                            SELECT "Hitesh" UNION ALL
                            SELECT "Shilpa" UNION ALL
                            SELECT "Rajesh" UNION ALL
                            SELECT "Aarti" UNION ALL
                            SELECT "Sumit" UNION ALL
                            SELECT "Sakshi" UNION ALL
                            SELECT "Sunil" UNION ALL
                            SELECT "Anjali" UNION ALL
                            SELECT "Rakesh" UNION ALL
                            SELECT "Simran") AS firstnames ORDER BY RAND() LIMIT 1),
        ' ',
        (SELECT name FROM (SELECT "Kumar" AS name UNION ALL
                            SELECT "Singh" UNION ALL
                            SELECT "Devi" UNION ALL
                            SELECT "Raj" UNION ALL
                            SELECT "Kumari" UNION ALL
                            SELECT "Patel" UNION ALL
                            SELECT "Kaur" UNION ALL
                            SELECT "Chandra" UNION ALL
                            SELECT "Sharma" UNION ALL
                            SELECT "Gupta") AS middlenames ORDER BY RAND() LIMIT 1),
        ' ',
        (SELECT name FROM (SELECT "Patel" AS name UNION ALL
                            SELECT "Sharma" UNION ALL
                            SELECT "Gupta" UNION ALL
                            SELECT "Singh" UNION ALL
                            SELECT "Kumar" UNION ALL
                            SELECT "Yadav" UNION ALL
                            SELECT "Jain" UNION ALL
                            SELECT "Gupta" UNION ALL
                            SELECT "Rao" UNION ALL
                            SELECT "Reddy" UNION ALL
                            SELECT "Choudhury" UNION ALL
                            SELECT "Pandey" UNION ALL
                            SELECT "Agarwal" UNION ALL
                            SELECT "Verma" UNION ALL
                            SELECT "Dixit" UNION ALL
                            SELECT "Mishra" UNION ALL
                            SELECT "Mehta" UNION ALL
                            SELECT "Shah" UNION ALL
                            SELECT "Khan" UNION ALL
                            SELECT "Das" UNION ALL
                            SELECT "Rajput" UNION ALL
                            SELECT "Biswas" UNION ALL
                            SELECT "Chatterjee" UNION ALL
                            SELECT "Malik" UNION ALL
                            SELECT "Ahmed" UNION ALL
                            SELECT "Malhotra" UNION ALL
                            SELECT "Kapoor" UNION ALL
                            SELECT "Sinha" UNION ALL
                            SELECT "Bhat" UNION ALL
                            SELECT "Nair" UNION ALL
                            SELECT "Iyer" UNION ALL
                            SELECT "Menon" UNION ALL
                            SELECT "Pillai" UNION ALL
                            SELECT "Menon" UNION ALL
                            SELECT "George" UNION ALL
                            SELECT "Thomas" UNION ALL
                            SELECT "Kamble" UNION ALL
                            SELECT "Pawar" UNION ALL
                            SELECT "Jadhav" UNION ALL
                            SELECT "Chavan" UNION ALL
                            SELECT "Deshmukh" UNION ALL
                            SELECT "Dutta" UNION ALL
                            SELECT "Barua" UNION ALL
                            SELECT "Goswami" UNION ALL
                            SELECT "Bose" UNION ALL
                            SELECT "Sen" UNION ALL
                            SELECT "Banerjee" UNION ALL
                            SELECT "Roy" UNION ALL
                            SELECT "Thakur") AS lastnames ORDER BY RAND() LIMIT 1)
    ),
    mobile_no = CONCAT(SUBSTRING(mobile_no, 1, LENGTH(mobile_no) - 4), LPAD(FLOOR(RAND() * 10000), 4, '0'));
   
    UPDATE m_address  set owner_number = CONCAT(SUBSTRING(owner_number, 1, LENGTH(owner_number) - 4), LPAD(FLOOR(RAND() * 10000), 4, '0'));

  
  
  
 UPDATE m_address 
SET
    address_line_1 = (SELECT address_line_1  FROM (SELECT "21 Chaura Rasta" AS address_line_1  UNION ALL
                                    SELECT "Sardar Bhawan" UNION ALL
                                    SELECT "D-96" UNION ALL
                                    SELECT "SA- 317" UNION ALL
                                    SELECT "3/26" UNION ALL
                                    SELECT "17 K 7" UNION ALL
                                    SELECT "15" UNION ALL
                                    SELECT "353" UNION ALL
                                    SELECT "Plot No. 1" UNION ALL
                                    SELECT "Baraf Khana" UNION ALL
                                    SELECT "E-691" UNION ALL
                                    SELECT "Kirti Nagar" UNION ALL
                                    SELECT "D-24" UNION ALL
                                    SELECT "Bhd Bata Shop" UNION ALL
                                    SELECT "Plot No. 2" UNION ALL
                                    SELECT "5/261" UNION ALL
                                    SELECT "Shakun Emporia" UNION ALL
                                    SELECT "29" UNION ALL
                                    SELECT "160" UNION ALL
                                    SELECT "E 770" UNION ALL
                                    SELECT "Girdhar Marg" UNION ALL
                                    SELECT "Vidhyut Nagar" UNION ALL
                                    SELECT "DCM" UNION ALL
                                    SELECT "Nakul Pats" UNION ALL
                                    SELECT "Makrana Mohalla" UNION ALL
                                    SELECT "Tunwarji Ka Jhalra Makrana Mohalla" UNION ALL
                                    SELECT "1st Floor Pal Haveli" UNION ALL
                                    SELECT "Dream Heights" UNION ALL
                                    SELECT "Backside Clock Tower" UNION ALL
                                    SELECT "651" UNION ALL
                                    SELECT "High Ct Rd" UNION ALL
                                    SELECT "Circuit House Rd" UNION ALL
                                    SELECT "Plot No. 5" UNION ALL
                                    SELECT "373" UNION ALL
                                    SELECT "The Fern Residency" UNION ALL
                                    SELECT "NH62" UNION ALL
                                    SELECT "Milkman Colony" UNION ALL
                                    SELECT "4th floor" UNION ALL
                                    SELECT "Circuit House Rd" UNION ALL
                                    SELECT "Hanwant Nagar" UNION ALL
                                    SELECT "Makrana Mohalla" UNION ALL
                                    SELECT "Plot no. 18" UNION ALL
                                    SELECT "UIT Rd" UNION ALL
                                    SELECT "9 A First floor Near PNB bank" UNION ALL
                                    SELECT "C1-8 Bhagyanagar" UNION ALL
                                    SELECT "105 Gold Souk" UNION ALL
                                    SELECT "701 Minoo Minar" UNION ALL
                                    SELECT "401 Distt Centre" UNION ALL
                                    SELECT "13 Gurukripa Bldg" UNION ALL
                                    SELECT "13, Gandhinagar") as address_line_1  ORDER BY RAND() LIMIT 1),
    address_line_2  = (SELECT address_line_2  FROM (SELECT "Chaura Rasta" AS address_line_2  UNION ALL
                                    SELECT "S-21 Bapu nagar" UNION ALL
                                    SELECT "Sukh Samridhi Apartment" UNION ALL
                                    SELECT "Jai Govind Complex" UNION ALL
                                    SELECT "Amer Rd" UNION ALL
                                    SELECT "Opp. HPCL Head Office" UNION ALL
                                    SELECT "Ajmer Rd Purani Chungi" UNION ALL
                                    SELECT "1st Floor Pragati Chamber" UNION ALL
                                    SELECT "Pinkcity House Enclave" UNION ALL
                                    SELECT "Lalkothi Scheme Lal Kothi" UNION ALL
                                    SELECT "Vasundhara Colony" UNION ALL
                                    SELECT "Shantipath" UNION ALL
                                    SELECT "M I Road" UNION ALL
                                    SELECT "Mysore House" UNION ALL
                                    SELECT "Baba Market" UNION ALL
                                    SELECT "Lalkothi Scheme" UNION ALL
                                    SELECT "Girdhar Marg" UNION ALL
                                    SELECT "Riktiya Bhairuji Temple" UNION ALL
                                    SELECT "Way to Fort" UNION ALL
                                    SELECT "CYB-5 RIICO Cyber Park" UNION ALL
                                    SELECT "Way to Fort" UNION ALL
                                    SELECT "opposite Suma Petrol Pump" UNION ALL
                                    SELECT "Mkt 1 Phase 2" UNION ALL
                                    SELECT "Evershine Nagar" UNION ALL
                                    SELECT "Roshan Mizil" UNION ALL
                                    SELECT "Beside Anmol Intl Chappel Road" UNION ALL
                                    SELECT "Street 5 Hari Nagar" UNION ALL
                                    SELECT "Jawahar Nagar Rd") AS address_line_2  ORDER BY RAND() LIMIT 1);
                                   
UPDATE m_bank_account_details  
set bank_account_number =  REPLACE (bank_account_number ,SUBSTRING(bank_account_number ,3,5),"XXXXX"),
 bank_ifsc_code =REPLACE (bank_ifsc_code  ,SUBSTRING(bank_ifsc_code ,2,4),"XXXX"),
 mobile_number  =CONCAT(SUBSTRING(mobile_number, 1, LENGTH(mobile_number) - 4), LPAD(FLOOR(RAND() * 10000), 4, '0'));
          
update m_client_family_member_incomes 
SET earning_pm = 
case when earning_pm between 5000 and 20000
then earning_pm+5000
when  earning_pm between 20000 and 50000
then earning_pm+10000
when earning_pm between 50000 and 75000
then earning_pm+12000
when earning_pm between 75000 and 100000
then earning_pm+15000
when earning_pm between 100000 and 150000
then earning_pm+20000
when earning_pm between   150000 and 300000
then earning_pm+22000
when earning_pm > 300000
then earning_pm+35000
end;



UPDATE  m_client_family_member_assets 
set asset_value=
case 
when asset_value  BETWEEN 10000 and 50000
then asset_value + 7500
when asset_value  BETWEEN  50000 and 100000
then asset_value  +17000
when asset_value  BETWEEN  100000 and 250000
then asset_value +23500
when asset_value  BETWEEN 250000 and 400000
then asset_value +33000
when asset_value BETWEEN 400000 and 600000
then asset_value +42500
when asset_value  >600000
then asset_value +57300
end;



UPDATE  m_client_family_member_liabilities
set amount=
case 
when amount  BETWEEN 10000 and 50000
then amount + 7500
when amount  BETWEEN  50000 and 100000
then amount  + 17000
when amount  BETWEEN  100000 and 250000
then amount + 23500
when amount  BETWEEN 250000 and 400000
then amount + 33000
when amount BETWEEN 400000 and 600000
then amount + 42500
when amount  between 600000 and 800000
then amount + 57300
when amount  between 800000 and 1000000
then amount + 45623
when amount  between 1000000 and 1500000
then amount + 55345
when amount  between 1500000 and 2100000
then amount + 65374
when amount > 2100000
then amount + 45366
end;

UPDATE  m_loan_assets
set asset_value=
case 
when asset_value  BETWEEN 10000 and 50000
then asset_value + 7500
when asset_value  BETWEEN  50000 and 100000
then asset_value  + 17000
when asset_value  BETWEEN  100000 and 250000
then asset_value + 23500
when asset_value  BETWEEN 250000 and 400000
then asset_value + 33000
when asset_value BETWEEN 400000 and 600000
then asset_value + 42500
when asset_value  between 600000 and 800000
then asset_value + 57300
when asset_value  between 800000 and 1000000
then asset_value + 45623
when asset_value  between 1000000 and 1500000
then asset_value + 55345
when asset_value  between 1500000 and 2100000
then asset_value + 65374
else asset_value
end ;




update m_bank_transaction_details 
set transaction_id =concat(left(transaction_id,2),"XXXX",right(transaction_id,2)),
narration=concat(left(narration,2),"XXXX",right(narration,2));



UPDATE m_collateral_valuation set
 valuater_remark = concat(LEFT(valuater_remark,2) , "XXXX",right(valuater_remark,2));

update m_collateral_valuation 
set value_of_collateral=
case when value_of_collateral between 0 and 5000
then value_of_collateral +442
when value_of_collateral between 5000 and 50000
then value_of_collateral +1589
when value_of_collateral between 50000 and 200000
then value_of_collateral+ 1748
when value_of_collateral >200000
then value_of_collateral +2356
else value_of_collateral
end;





update m_appuser 
set email='thedarji.creations@gmail.com';


UPDATE m_liabilities set security_details=
 concat(LEFT(security_details,2) , "XXXX",right(security_details,2));





UPDATE m_client_family_member_assets set
 asset_detail = concat(LEFT(asset_detail,2) , "XXXX",right(asset_detail,2));


update m_property_type_collateral 
set land_value=
case when land_value between 0 and 5000
then land_value +442
when land_value between 5000 and 50000
then land_value +1589
when land_value between 50000 and 200000
then land_value+ 1748
when land_value >200000
then land_value +2356
else land_value
end,
construction_value=
case when construction_value between 0 and 5000
then construction_value +442
when construction_value between 5000 and 50000
then construction_value +1589
when construction_value between 50000 and 200000
then construction_value+ 1748
when construction_value >200000
then construction_value +2356
else construction_value
end,
total_value=land_value+construction_value;


update r_task_query 
set query_by=replace(query_by, substring(query_by,1,locate("@", query_by)),"XYZ@"),
resolved_by=replace(resolved_by, substring(resolved_by,1,locate("@", resolved_by)),"XYZ@");



UPDATE m_note set note=
 concat(LEFT(note,2) , "XXXX",right(note,2));



UPDATE m_mitigation  set mitigation_description=
 concat(LEFT(mitigation_description,2) , "XXXX",right(mitigation_description,2));


UPDATE m_deviation  set deviation_reason=
 concat(LEFT(deviation_reason,3) , "XXXX",right(deviation_reason,2));


	UPDATE m_kyc set
 validate_json_data = concat(LEFT(validate_json_data,4) , "XXXX",right(validate_json_data,4))
 where validate_json_data is not null;
 UPDATE m_kyc set
 ocr_json=concat(LEFT(ocr_json,4) , "XXXX",right(ocr_json,4)) 
 where ocr_json is not null;
 
 	UPDATE m_kyc_entity set
ocr_json_data = concat(LEFT(ocr_json_data,4) , "XXXX",right(ocr_json_data,4))
 where ocr_json_data is not null;
 UPDATE m_kyc_entity set
 validate_json_data=concat(LEFT(validate_json_data,4) , "XXXX",right(validate_json_data,4)) 
 where validate_json_data is not null;
 
 update m_credit_report_manual set
  name = CONCAT(
        (SELECT name FROM (SELECT "Priya" AS name UNION ALL
                            SELECT "Rahul" UNION ALL
                            SELECT "Anika" UNION ALL
                            SELECT "Rohit" UNION ALL
                            SELECT "Aisha" UNION ALL
                            SELECT "Arjun" UNION ALL
                            SELECT "Neha" UNION ALL
                            SELECT "Raj" UNION ALL
                            SELECT "Shreya" UNION ALL
                            SELECT "Vishal" UNION ALL
                            SELECT "Aarav" UNION ALL
                            SELECT "Pooja" UNION ALL
                            SELECT "Vikram" UNION ALL
                            SELECT "Meera" UNION ALL
                            SELECT "Sanjay" UNION ALL
                            SELECT "Riya" UNION ALL
                            SELECT "Sameer" UNION ALL
                            SELECT "Nisha" UNION ALL
                            SELECT "Aditya" UNION ALL
                            SELECT "Komal" UNION ALL
                            SELECT "Siddharth" UNION ALL
                            SELECT "Kavita" UNION ALL
                            SELECT "Akash" UNION ALL
                            SELECT "Ritu" UNION ALL
                            SELECT "Prateek" UNION ALL
                            SELECT "Divya" UNION ALL
                            SELECT "Abhishek" UNION ALL
                            SELECT "Maya" UNION ALL
                            SELECT "Karan" UNION ALL
                            SELECT "Sneha" UNION ALL
                            SELECT "Yash" UNION ALL
                            SELECT "Nidhi" UNION ALL
                            SELECT "Suresh" UNION ALL
                            SELECT "Manisha" UNION ALL
                            SELECT "Amit" UNION ALL
                            SELECT "Swati" UNION ALL
                            SELECT "Ravi" UNION ALL
                            SELECT "Mona" UNION ALL
                            SELECT "Arun" UNION ALL
                            SELECT "Radha" UNION ALL
                            SELECT "Hitesh" UNION ALL
                            SELECT "Shilpa" UNION ALL
                            SELECT "Rajesh" UNION ALL
                            SELECT "Aarti" UNION ALL
                            SELECT "Sumit" UNION ALL
                            SELECT "Sakshi" UNION ALL
                            SELECT "Sunil" UNION ALL
                            SELECT "Anjali" UNION ALL
                            SELECT "Rakesh" UNION ALL
                            SELECT "Simran") AS firstnames ORDER BY RAND() LIMIT 1),
        ' ',
        (SELECT name FROM (SELECT "Patel" AS name UNION ALL
                            SELECT "Sharma" UNION ALL
                            SELECT "Gupta" UNION ALL
                            SELECT "Singh" UNION ALL
                            SELECT "Kumar" UNION ALL
                            SELECT "Yadav" UNION ALL
                            SELECT "Jain" UNION ALL
                            SELECT "Gupta" UNION ALL
                            SELECT "Rao" UNION ALL
                            SELECT "Reddy" UNION ALL
                            SELECT "Choudhury" UNION ALL
                            SELECT "Pandey" UNION ALL
                            SELECT "Agarwal" UNION ALL
                            SELECT "Verma" UNION ALL
                            SELECT "Dixit" UNION ALL
                            SELECT "Mishra" UNION ALL
                            SELECT "Mehta" UNION ALL
                            SELECT "Shah" UNION ALL
                            SELECT "Khan" UNION ALL
                            SELECT "Das" UNION ALL
                            SELECT "Rajput" UNION ALL
                            SELECT "Biswas" UNION ALL
                            SELECT "Chatterjee" UNION ALL
                            SELECT "Malik" UNION ALL
                            SELECT "Ahmed" UNION ALL
                            SELECT "Malhotra" UNION ALL
                            SELECT "Kapoor" UNION ALL
                            SELECT "Sinha" UNION ALL
                            SELECT "Bhat" UNION ALL
                            SELECT "Nair" UNION ALL
                            SELECT "Iyer" UNION ALL
                            SELECT "Menon" UNION ALL
                            SELECT "Pillai" UNION ALL
                            SELECT "Menon" UNION ALL
                            SELECT "George" UNION ALL
                            SELECT "Thomas" UNION ALL
                            SELECT "Kamble" UNION ALL
                            SELECT "Pawar" UNION ALL
                            SELECT "Jadhav" UNION ALL
                            SELECT "Chavan" UNION ALL
                            SELECT "Deshmukh" UNION ALL
                            SELECT "Dutta" UNION ALL
                            SELECT "Barua" UNION ALL
                            SELECT "Goswami" UNION ALL
                            SELECT "Bose" UNION ALL
                            SELECT "Sen" UNION ALL
                            SELECT "Banerjee" UNION ALL
                            SELECT "Roy" UNION ALL
                            SELECT "Thakur") AS lastnames ORDER BY RAND() LIMIT 1)
    );
   
   
UPDATE m_staff  set mobile_no = CONCAT(SUBSTRING(mobile_no, 1, LENGTH(mobile_no) - 4), LPAD(FLOOR(RAND() * 10000), 4, '0'));




update m_loan_assets  set
  asset_detail =
(select asset_detail from (
 select "2021 Toyota Camry, 4-door sedan, 30,000 km"  union all
select "2020 Honda Accord, 2-door coupe, 25,000 km" union all
select "2019 Ford F-150, 4x4 pickup, 40,000 km" union all
select "2018 Chevrolet Tahoe, full-size SUV, 50,000 km" union all
select "2022 Tesla Model 3, electric sedan, 10,000 km" union all
select "2020 BMW 3 Series, luxury sedan, 20,000 km" union all
select "2021 Audi Q5, compact SUV, 15,000 km" union all
select "2019 Jeep Wrangler, off-road SUV, 35,000 km" union all
select "2018 Subaru Outback, AWD wagon, 45,000 km" union all
select "2022 Nissan Leaf, electric hatchback, 5,000 km" union all
select "2020 Mercedes-Benz GLC, compact luxury SUV, 18,000 km" union all
select "2019 Lexus RX, mid-size luxury SUV, 30,000 km" union all
select "2021 Honda CR-V, compact SUV, 12,000 km" union all
select "2020 Kia Sorento, mid-size SUV, 25,000 km" union all
select "2019 Hyundai Tucson, compact SUV, 35,000 km" union all
select "2021 Ford Mustang, sports car, 10,000 km" union all
select "2020 Dodge Charger, full-size sedan, 22,000 km" union all
select "2018 GMC Sierra, 4x4 pickup, 50,000 km" union all
select "2019 Volkswagen Jetta, compact sedan, 30,000 km" union all
select "2022 Chevrolet Bolt, electric car, 7,000 km" union all
select "2021 Volvo XC60, luxury SUV, 12,000 km" union all
select "2020 Mazda CX-5, compact SUV, 20,000 km" union all
select "2019 Acura MDX, luxury SUV, 28,000 km" union all
select "2018 Ram 1500, 4x4 pickup, 45,000 km" union all
select "2022 Hyundai Kona, electric SUV, 6,000 km" union all
select "3-bedroom, 2-bathroom single-family home, 2,000 sq ft" union all
select "4-bedroom, 3-bathroom townhouse, 1,800 sq ft" union all
select "2-bedroom, 1-bathroom condominium, 1,200 sq ft" union all
select "5-bedroom, 4-bathroom single-family home, 3,000 sq ft" union all
select "3-bedroom, 2-bathroom ranch-style home, 1,600 sq ft" union all
select "4-bedroom, 3-bathroom colonial-style home, 2,500 sq ft" union all
select "2-bedroom, 2-bathroom loft, 1,400 sq ft" union all
select "3-bedroom, 2-bathroom duplex, 1,800 sq ft" union all
select "4-bedroom, 2.5-bathroom split-level home, 2,200 sq ft" union all
select "3-bedroom, 2-bathroom cape cod-style home, 1,700 sq ft" union all
select "5-bedroom, 3.5-bathroom Victorian-style home, 3,500 sq ft" union all
select "2-bedroom, 1.5-bathroom cottage, 1,100 sq ft" union all
select "3-bedroom, 3-bathroom penthouse apartment, 2,200 sq ft" union all
select "4-bedroom, 3-bathroom Mediterranean-style home, 2,800 sq ft" union all
select "3-bedroom, 2.5-bathroom contemporary home, 2,000 sq ft" union all
select "4-bedroom, 3.5-bathroom craftsman-style home, 2,600 sq ft" union all
select "2-bedroom, 2-bathroom high-rise condo, 1,300 sq ft" union all
select "5-bedroom, 4-bathroom Tudor-style home, 3,200 sq ft" union all
select "3-bedroom, 2-bathroom bungalow, 1,500 sq ft" union all
select "4-bedroom, 3-bathroom ranch-style home, 2,100 sq ft" union all
select "3-bedroom, 2.5-bathroom townhouse, 1,700 sq ft" union all
select "2-bedroom, 1-bathroom garden apartment, 1,000 sq ft" union all
select "4-bedroom, 3.5-bathroom colonial-style home, 2,700 sq ft" union all
select "3-bedroom, 2-bathroom single-family home, 1,800 sq ft" union all
select "5-bedroom, 3-bathroom split-level home, 3,000 sq ft" union all 
select "2021 Maruti Suzuki Swift, hatchback, 20,000 km" union all
select "2020 Hyundai Creta, SUV, 25,000 km" union all
select "2019 Mahindra Scorpio, SUV, 40,000 km" union all
select "2018 Tata Tiago, hatchback, 30,000 km" union all
select "2022 Toyota Innova Crysta, MPV, 10,000 km" union all
select "2020 Honda City, sedan, 15,000 km" union all
select "2021 Kia Seltos, SUV, 12,000 km" union all
select "2019 Royal Enfield Classic 350, motorcycle, 15,000 km" union all
select "2018 Bajaj Pulsar 150, motorcycle, 25,000 km" union all
select "2022 Tata Nexon, compact SUV, 5,000 km" union all
select "2020 Maruti Suzuki Baleno, hatchback,18,000 km" union all
select "2019 Hyundai Verna, sedan, 20,000 km" union all
select "2021 Mahindra XUV500, SUV, 14,000 km" union all
select "2020 Bajaj Chetak, electric scooter, 10,000 km" union all
select "2019 TVS Jupiter, scooter, 22,000 km" union all
select "2021 Hero Splendor Plus, motorcycle, 8,000 km" union all
select "2020 Hyundai Venue, compact SUV, 17,000 km" union all
select "2018 Honda Activa 5G, scooter, 28,000 km" union all
select "2019 Suzuki Access 125, scooter, 16,000 km" union all
select "2022 MG Hector, SUV, 7,000 km" union all
select "2021 Skoda Rapid, sedan, 12,000 km" union all
select "2020 Renault Kwid, hatchback, 13,000 km" union all
select "2019 Ford EcoSport, SUV, 30,000 km" union all
select "2018 Yamaha FZ S V3, motorcycle, 24,000 km" union all
select "2022 Nissan Magnite, compact SUV, 6,000 km" 
)AS asset_detail ORDER BY RAND() LIMIT 1);




