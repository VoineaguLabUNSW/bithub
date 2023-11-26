# Deployment Instructions

The standard commands `terraform init` and `terraform apply` can be used to replicate the S3/Cloudfront setup used by BIThub on any AWS account, but the aws profile/region and s3 bucket name may need to be changed.

After deploying, the cloudfront URL from the aws console needs to be manually provided in the input.yaml.