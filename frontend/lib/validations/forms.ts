import { z } from 'zod'

// AWS 12-digit Account ID regex
export const AWS_ACCOUNT_ID_REGEX = /^\d{12}$/

// AWS IAM Role ARN regex: arn:aws:iam::123456789012:role/RoleName
export const AWS_ROLE_ARN_REGEX = /^arn:aws:iam::\d{12}:role\/[\w+=,.@\-_/]+$/

// Standard AWS Region regex: e.g. us-east-1, ap-south-1
export const AWS_REGION_REGEX = /^[a-z]{2}(-[a-z]+)+-\d{1}$/

// Basic validation primitives
export const awsAccountIdSchema = z
  .string()
  .trim()
  .regex(AWS_ACCOUNT_ID_REGEX, {
    message: 'AWS Account ID must be exactly 12 digits (e.g. 123456789012)',
  })

export const awsRoleArnSchema = z
  .string()
  .trim()
  .regex(AWS_ROLE_ARN_REGEX, {
    message: 'Must be a valid AWS IAM Role ARN (e.g. arn:aws:iam::123456789012:role/CloudPulseRole)',
  })

export const awsRegionSchema = z
  .string()
  .trim()
  .min(1, 'Region is required')
  .regex(AWS_REGION_REGEX, {
    message: 'Must be a valid AWS region identifier (e.g. us-east-1, ap-south-1)',
  })

// Fleet Account Enrollment Schema
export const enrollAccountSchema = z.object({
  account_id: awsAccountIdSchema,
  account_name: z
    .string()
    .trim()
    .min(2, 'Account name must be at least 2 characters')
    .max(64, 'Account name cannot exceed 64 characters'),
  region: awsRegionSchema,
  role_arn: awsRoleArnSchema.optional().or(z.literal('')),
  is_management_account: z.boolean().default(false),
})

export type EnrollAccountInput = z.infer<typeof enrollAccountSchema>

// Cloud Connection Form Schema (ConnectModal)
export const connectCloudSchema = z.discriminatedUnion('auth_method', [
  // 1. Learner Lab / Temporary STS Credentials
  z.object({
    provider: z.literal('AWS'),
    auth_method: z.literal('learner_lab'),
    account_name: z.string().trim().min(2, 'Account name is required'),
    region: awsRegionSchema,
    access_key_id: z.string().trim().min(16, 'Access Key ID must be at least 16 characters'),
    secret_access_key: z.string().trim().min(20, 'Secret Access Key must be at least 20 characters'),
    session_token: z.string().trim().min(20, 'Session Token is required for Learner Lab / STS credentials'),
  }),
  // 2. IAM AssumeRole (Cross-Account Security Best Practice)
  z.object({
    provider: z.literal('AWS'),
    auth_method: z.literal('iam_role'),
    account_name: z.string().trim().min(2, 'Account name is required'),
    region: awsRegionSchema,
    role_arn: awsRoleArnSchema,
    external_id: z.string().trim().optional(),
  }),
  // 3. Static IAM User Keys
  z.object({
    provider: z.literal('AWS'),
    auth_method: z.literal('keys'),
    account_name: z.string().trim().min(2, 'Account name is required'),
    region: awsRegionSchema,
    access_key_id: z.string().trim().min(16, 'Access Key ID must be at least 16 characters'),
    secret_access_key: z.string().trim().min(20, 'Secret Access Key must be at least 20 characters'),
  }),
])

export type ConnectCloudInput = z.infer<typeof connectCloudSchema>

// Schedule & Pre-Warming Configuration Schema
export const schedulerConfigSchema = z.object({
  schedule_name: z.string().trim().min(3, 'Schedule name must be at least 3 characters'),
  cron_expression: z
    .string()
    .trim()
    .min(9, 'Must be a valid 5 or 6 token cron expression')
    .regex(/^(\S+\s+){4,5}\S+$/, 'Invalid cron expression format (e.g. 0 8 * * 1-5)'),
  target_instance_ids: z.array(z.string().trim().min(5)).min(1, 'Select at least one instance to schedule'),
  prewarm_lead_minutes: z.number().int().min(5, 'Lead time must be at least 5 minutes').max(120, 'Lead time cannot exceed 120 minutes'),
  enabled: z.boolean().default(true),
})

export type SchedulerConfigInput = z.infer<typeof schedulerConfigSchema>

// Generic Form Validator Helper
export interface ValidationResult<T> {
  success: boolean
  data?: T
  errors: Record<string, string>
}

export function validateForm<T>(schema: z.ZodSchema<T>, data: unknown): ValidationResult<T> {
  const result = schema.safeParse(data)
  if (result.success) {
    return { success: true, data: result.data, errors: {} }
  }

  const errors: Record<string, string> = {}
  result.error.issues.forEach((issue) => {
    const fieldName = issue.path.join('.') || 'root'
    if (!errors[fieldName]) {
      errors[fieldName] = issue.message
    }
  })

  return { success: false, errors }
}
