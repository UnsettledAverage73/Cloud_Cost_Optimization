import { describe, it, expect } from 'vitest'
import {
  awsAccountIdSchema,
  awsRoleArnSchema,
  awsRegionSchema,
  enrollAccountSchema,
  connectCloudSchema,
  schedulerConfigSchema,
  validateForm,
} from '@/lib/validations/forms'

describe('Form Validation Schemas (Zod)', () => {
  describe('AWS Account ID Schema', () => {
    it('accepts valid 12-digit account IDs', () => {
      const result = awsAccountIdSchema.safeParse('123456789012')
      expect(result.success).toBe(true)
    })

    it('rejects account IDs with fewer than 12 digits', () => {
      const result = awsAccountIdSchema.safeParse('12345678901')
      expect(result.success).toBe(false)
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('12 digits')
      }
    })

    it('rejects account IDs with letters or special characters', () => {
      const result = awsAccountIdSchema.safeParse('12345678901a')
      expect(result.success).toBe(false)
    })
  })

  describe('AWS Role ARN Schema', () => {
    it('accepts valid AWS IAM Role ARNs', () => {
      const validArn = 'arn:aws:iam::123456789012:role/CloudPulseReadOnlyRole'
      const result = awsRoleArnSchema.safeParse(validArn)
      expect(result.success).toBe(true)
    })

    it('rejects malformed ARNs', () => {
      const invalidArn = 'not:an:arn:format'
      const result = awsRoleArnSchema.safeParse(invalidArn)
      expect(result.success).toBe(false)
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('valid AWS IAM Role ARN')
      }
    })
  })

  describe('AWS Region Schema', () => {
    it('accepts standard AWS region names', () => {
      expect(awsRegionSchema.safeParse('us-east-1').success).toBe(true)
      expect(awsRegionSchema.safeParse('ap-south-1').success).toBe(true)
      expect(awsRegionSchema.safeParse('eu-west-2').success).toBe(true)
    })

    it('rejects invalid region strings', () => {
      expect(awsRegionSchema.safeParse('').success).toBe(false)
      expect(awsRegionSchema.safeParse('invalid_region').success).toBe(false)
    })
  })

  describe('Fleet Account Enrollment Schema', () => {
    it('validates a correct fleet account payload', () => {
      const valid = {
        account_id: '123456789012',
        account_name: 'Production Core',
        region: 'us-east-1',
        role_arn: 'arn:aws:iam::123456789012:role/OrgRole',
        is_management_account: false,
      }
      const res = validateForm(enrollAccountSchema, valid)
      expect(res.success).toBe(true)
      expect(res.data?.account_name).toBe('Production Core')
    })

    it('catches invalid account IDs and short names', () => {
      const invalid = {
        account_id: '123',
        account_name: 'A',
        region: 'invalid',
      }
      const res = validateForm(enrollAccountSchema, invalid)
      expect(res.success).toBe(false)
      expect(res.errors['account_id']).toBeDefined()
      expect(res.errors['account_name']).toBeDefined()
      expect(res.errors['region']).toBeDefined()
    })
  })

  describe('Cloud Connection Schema (Discriminated Union)', () => {
    it('validates Learner Lab credentials with session token', () => {
      const payload = {
        provider: 'AWS',
        auth_method: 'learner_lab',
        account_name: 'Learner Sandbox',
        region: 'us-east-1',
        access_key_id: 'ASIAIOSFODNN7EXAMPLE',
        secret_access_key: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        session_token: 'IQoJb3JpZ2luX2VjEJr//////////wEaCXVzLWVhc3QtMSJHMEUCIQ...',
      }
      const res = validateForm(connectCloudSchema, payload)
      expect(res.success).toBe(true)
    })

    it('rejects Learner Lab credentials when session token is missing', () => {
      const payload = {
        provider: 'AWS',
        auth_method: 'learner_lab',
        account_name: 'Learner Sandbox',
        region: 'us-east-1',
        access_key_id: 'ASIAIOSFODNN7EXAMPLE',
        secret_access_key: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        session_token: '',
      }
      const res = validateForm(connectCloudSchema, payload)
      expect(res.success).toBe(false)
      expect(res.errors['session_token']).toBeDefined()
    })

    it('validates IAM AssumeRole configuration', () => {
      const payload = {
        provider: 'AWS',
        auth_method: 'iam_role',
        account_name: 'FinOps Member Account',
        region: 'us-east-1',
        role_arn: 'arn:aws:iam::123456789012:role/CloudPulseRole',
      }
      const res = validateForm(connectCloudSchema, payload)
      expect(res.success).toBe(true)
    })
  })

  describe('Scheduler & Prewarm Configuration Schema', () => {
    it('validates cron expression and instance selection', () => {
      const payload = {
        schedule_name: 'Weekday Dev Warmup',
        cron_expression: '0 8 * * 1-5',
        target_instance_ids: ['i-0abcd1234efgh5678'],
        prewarm_lead_minutes: 15,
        enabled: true,
      }
      const res = validateForm(schedulerConfigSchema, payload)
      expect(res.success).toBe(true)
    })

    it('rejects invalid cron expression and empty instance targets', () => {
      const payload = {
        schedule_name: 'AB',
        cron_expression: 'not-a-cron',
        target_instance_ids: [],
        prewarm_lead_minutes: 2,
        enabled: true,
      }
      const res = validateForm(schedulerConfigSchema, payload)
      expect(res.success).toBe(false)
      expect(res.errors['schedule_name']).toBeDefined()
      expect(res.errors['cron_expression']).toBeDefined()
      expect(res.errors['target_instance_ids']).toBeDefined()
      expect(res.errors['prewarm_lead_minutes']).toBeDefined()
    })
  })
})
