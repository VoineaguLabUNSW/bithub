terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = "us-east-1"
  profile = "bithub-permissions-790772245098"
}

resource "aws_s3_bucket" "my_app" {
  bucket = "bithub-bucket"
}

resource "aws_s3_bucket_public_access_block" "my_app" {
  bucket = aws_s3_bucket.my_app.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "my_app" {
  bucket = "${aws_s3_bucket.my_app.id}"
  policy = "${data.aws_iam_policy_document.my_app.json}"
}

resource "aws_s3_bucket_cors_configuration" "my_app" {
  bucket = "${aws_s3_bucket.my_app.id}"

  cors_rule {
    allowed_methods = ["GET"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_cloudfront_origin_access_identity" "my_app" {
}

data "aws_iam_policy_document" "my_app" {
  statement {
    actions = ["s3:GetObject"]
    principals {
      type        = "AWS"
      identifiers = ["${aws_cloudfront_origin_access_identity.my_app.iam_arn}"]
    }
    resources = ["${aws_s3_bucket.my_app.arn}/*"]
  }
}

resource "aws_cloudfront_distribution" "my_app" {
  enabled             = true
  is_ipv6_enabled     = true
  wait_for_deployment = true
  price_class         = "PriceClass_All"

  origin {
    domain_name = "${aws_s3_bucket.my_app.bucket_regional_domain_name}"
    origin_id   = "my_app_origin"
    s3_origin_config {
      origin_access_identity = "${aws_cloudfront_origin_access_identity.my_app.cloudfront_access_identity_path}"
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD", "OPTIONS"]
    target_origin_id = "my_app_origin"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
      headers = ["Origin", "Cache-Control", "ETag"]
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400

  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
}

output "cloudfront_url" {
  value = aws_cloudfront_distribution.my_app.domain_name
  description = "The URL of the CloudFront distribution, add to input.yaml"
}