set sql_safe_updates=0;
UPDATE c_configuration SET enabled = 0 WHERE name = 'amazon-S3';
UPDATE c_external_service_properties set value = 'demo' where name = 's3_access_key';
UPDATE c_external_service_properties set value = 'demo' where name = 's3_bucket_name';
UPDATE c_external_service_properties set value = 'demo' where name = 's3_secret_key';
truncate external_services_config;
truncate c_external_service_properties;
UPDATE c_external_service_properties set value = 'demo' where name = 'username';
UPDATE c_external_service_properties set value = 'demo' where name = 'password';
 
update c_external_service_properties
set value='https://services.graviton.kugelblitz.in/utility/stateandcity'
where name='states_url';
 
update c_external_service_properties
set value='https://services.graviton.kugelblitz.in/utility/pincode'
where name='address_by_pincode_url';