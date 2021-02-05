# Tidepool Big Data Donation Project

## How to use this code

This code is a refactor of the `data-donation-pipeline` to perform common
operations for the Tidepool Big Data Donation Project.

Common operations include:

* Accepting donation share invitations to the project and partner account
* Summarizing the user population that has shared
* Determining donation amounts to partners
* Creating data sets for research

## Login

To use the code for the TBDDP, you need access to the project and partner
institution auth key/values, which are located in the Tidepool 1Password
BigData vault. For security purposes, follow this process for logging in:

* Login to 1Password
* Find the auth file in the Big Data vault called .env
* Create a symlink in this folder to that file with this command
    * `ln -s <path to env file> tbddp.auth`
* Run the code in these files

Note: You need to logged into 1Password for this code to access the auth file.
