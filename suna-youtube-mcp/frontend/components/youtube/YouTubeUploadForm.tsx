/**
 * YouTube Upload Form Component
 * Uses React Hook Form with Zod validation following Suna's tech stack
 */

import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import * as Dialog from '@radix-ui/react-dialog'
import * as Label from '@radix-ui/react-label'
import * as Select from '@radix-ui/react-select'
import * as Switch from '@radix-ui/react-switch'
import { Upload, X, ChevronDown, Check } from 'lucide-react'
import { useInitiateUpload, usePrepareUpload } from '@/hooks/useYouTubeChannels'
import { YOUTUBE_CATEGORIES, PrivacyStatus } from '@/lib/youtube/types'
import { cn } from '@/lib/utils'

// Zod schema for form validation
const uploadSchema = z.object({
  title: z.string()
    .min(1, 'Title is required')
    .max(100, 'Title must be 100 characters or less'),
  description: z.string()
    .max(5000, 'Description must be 5000 characters or less')
    .optional(),
  tags: z.string()
    .optional()
    .transform((val) => val ? val.split(',').map(t => t.trim()).filter(Boolean) : [])
    .refine((tags) => {
      const totalChars = tags.join('').length
      return totalChars <= 500
    }, 'Total tag characters must be 500 or less'),
  categoryId: z.string().default('22'),
  privacyStatus: z.nativeEnum(PrivacyStatus).default(PrivacyStatus.PRIVATE),
  madeForKids: z.boolean().default(false),
  notifySubscribers: z.boolean().default(true),
})

type UploadFormData = z.infer<typeof uploadSchema>

interface YouTubeUploadFormProps {
  channelId: string
  onSuccess?: (uploadId: string) => void
  onCancel?: () => void
}

export function YouTubeUploadForm({ channelId, onSuccess, onCancel }: YouTubeUploadFormProps) {
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [thumbnailFile, setThumbnailFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  const prepareUpload = usePrepareUpload()
  const initiateUpload = useInitiateUpload()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setValue,
    watch,
  } = useForm<UploadFormData>({
    resolver: zodResolver(uploadSchema),
    defaultValues: {
      privacyStatus: PrivacyStatus.PRIVATE,
      categoryId: '22',
      madeForKids: false,
      notifySubscribers: true,
    },
  })

  const selectedCategory = watch('categoryId')
  const selectedPrivacy = watch('privacyStatus')
  const madeForKids = watch('madeForKids')
  const notifySubscribers = watch('notifySubscribers')

  const onSubmit = async (data: UploadFormData) => {
    if (!videoFile) {
      alert('Please select a video file')
      return
    }

    setIsUploading(true)

    try {
      // Prepare video file
      const videoRef = await prepareUpload.mutateAsync({
        file: videoFile,
        fileType: 'video',
      })

      // Prepare thumbnail if provided
      let thumbnailRef = null
      if (thumbnailFile) {
        thumbnailRef = await prepareUpload.mutateAsync({
          file: thumbnailFile,
          fileType: 'thumbnail',
        })
      }

      // Initiate upload
      const uploadResult = await initiateUpload.mutateAsync({
        channelId,
        referenceId: videoRef.reference_id,
        metadata: {
          title: data.title,
          description: data.description || '',
          tags: data.tags || [],
          category_id: data.categoryId,
          privacy_status: data.privacyStatus,
          made_for_kids: data.madeForKids,
          notify_subscribers: data.notifySubscribers,
        },
      })

      onSuccess?.(uploadResult.upload_id)
    } catch (error) {
      console.error('Upload failed:', error)
      alert('Upload failed. Please try again.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Video File Input */}
      <div>
        <Label.Root htmlFor="video-file" className="block text-sm font-medium mb-2">
          Video File *
        </Label.Root>
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
          <input
            id="video-file"
            type="file"
            accept="video/*"
            onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
            className="hidden"
          />
          <label
            htmlFor="video-file"
            className="cursor-pointer flex flex-col items-center"
          >
            <Upload className="h-12 w-12 text-gray-400 mb-2" />
            <span className="text-sm text-gray-600">
              {videoFile ? videoFile.name : 'Click to select video'}
            </span>
            {videoFile && (
              <span className="text-xs text-gray-500 mt-1">
                {(videoFile.size / (1024 * 1024)).toFixed(2)} MB
              </span>
            )}
          </label>
        </div>
      </div>

      {/* Thumbnail File Input */}
      <div>
        <Label.Root htmlFor="thumbnail-file" className="block text-sm font-medium mb-2">
          Thumbnail (Optional)
        </Label.Root>
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center">
          <input
            id="thumbnail-file"
            type="file"
            accept="image/*"
            onChange={(e) => setThumbnailFile(e.target.files?.[0] || null)}
            className="hidden"
          />
          <label
            htmlFor="thumbnail-file"
            className="cursor-pointer flex items-center justify-center"
          >
            <span className="text-sm text-gray-600">
              {thumbnailFile ? thumbnailFile.name : 'Select thumbnail image'}
            </span>
          </label>
        </div>
      </div>

      {/* Title Input */}
      <div>
        <Label.Root htmlFor="title" className="block text-sm font-medium mb-2">
          Title *
        </Label.Root>
        <input
          id="title"
          type="text"
          {...register('title')}
          className={cn(
            'w-full px-3 py-2 border rounded-md',
            'focus:outline-none focus:ring-2 focus:ring-blue-500',
            errors.title && 'border-red-500'
          )}
          placeholder="Enter video title"
        />
        {errors.title && (
          <p className="mt-1 text-sm text-red-600">{errors.title.message}</p>
        )}
      </div>

      {/* Description Input */}
      <div>
        <Label.Root htmlFor="description" className="block text-sm font-medium mb-2">
          Description
        </Label.Root>
        <textarea
          id="description"
          {...register('description')}
          rows={4}
          className={cn(
            'w-full px-3 py-2 border rounded-md',
            'focus:outline-none focus:ring-2 focus:ring-blue-500',
            errors.description && 'border-red-500'
          )}
          placeholder="Enter video description"
        />
        {errors.description && (
          <p className="mt-1 text-sm text-red-600">{errors.description.message}</p>
        )}
      </div>

      {/* Tags Input */}
      <div>
        <Label.Root htmlFor="tags" className="block text-sm font-medium mb-2">
          Tags
        </Label.Root>
        <input
          id="tags"
          type="text"
          {...register('tags')}
          className={cn(
            'w-full px-3 py-2 border rounded-md',
            'focus:outline-none focus:ring-2 focus:ring-blue-500',
            errors.tags && 'border-red-500'
          )}
          placeholder="Enter tags separated by commas"
        />
        {errors.tags && (
          <p className="mt-1 text-sm text-red-600">{errors.tags.message}</p>
        )}
      </div>

      {/* Category Select */}
      <div>
        <Label.Root className="block text-sm font-medium mb-2">
          Category
        </Label.Root>
        <Select.Root value={selectedCategory} onValueChange={(value) => setValue('categoryId', value)}>
          <Select.Trigger className="w-full px-3 py-2 border rounded-md flex items-center justify-between">
            <Select.Value>
              {YOUTUBE_CATEGORIES.find(c => c.id === selectedCategory)?.title || 'Select category'}
            </Select.Value>
            <Select.Icon>
              <ChevronDown className="h-4 w-4" />
            </Select.Icon>
          </Select.Trigger>
          <Select.Portal>
            <Select.Content className="bg-white border rounded-md shadow-lg">
              <Select.Viewport className="p-1">
                {YOUTUBE_CATEGORIES.map((category) => (
                  <Select.Item
                    key={category.id}
                    value={category.id}
                    className="px-3 py-2 hover:bg-gray-100 cursor-pointer flex items-center justify-between"
                  >
                    <Select.ItemText>{category.title}</Select.ItemText>
                    <Select.ItemIndicator>
                      <Check className="h-4 w-4" />
                    </Select.ItemIndicator>
                  </Select.Item>
                ))}
              </Select.Viewport>
            </Select.Content>
          </Select.Portal>
        </Select.Root>
      </div>

      {/* Privacy Status Select */}
      <div>
        <Label.Root className="block text-sm font-medium mb-2">
          Privacy Status
        </Label.Root>
        <Select.Root value={selectedPrivacy} onValueChange={(value) => setValue('privacyStatus', value as PrivacyStatus)}>
          <Select.Trigger className="w-full px-3 py-2 border rounded-md flex items-center justify-between">
            <Select.Value>{selectedPrivacy}</Select.Value>
            <Select.Icon>
              <ChevronDown className="h-4 w-4" />
            </Select.Icon>
          </Select.Trigger>
          <Select.Portal>
            <Select.Content className="bg-white border rounded-md shadow-lg">
              <Select.Viewport className="p-1">
                {Object.values(PrivacyStatus).map((status) => (
                  <Select.Item
                    key={status}
                    value={status}
                    className="px-3 py-2 hover:bg-gray-100 cursor-pointer flex items-center justify-between"
                  >
                    <Select.ItemText>{status}</Select.ItemText>
                    <Select.ItemIndicator>
                      <Check className="h-4 w-4" />
                    </Select.ItemIndicator>
                  </Select.Item>
                ))}
              </Select.Viewport>
            </Select.Content>
          </Select.Portal>
        </Select.Root>
      </div>

      {/* Made for Kids Switch */}
      <div className="flex items-center justify-between">
        <Label.Root htmlFor="made-for-kids" className="text-sm font-medium">
          Made for Kids
        </Label.Root>
        <Switch.Root
          id="made-for-kids"
          checked={madeForKids}
          onCheckedChange={(checked) => setValue('madeForKids', checked)}
          className="w-11 h-6 bg-gray-200 rounded-full relative data-[state=checked]:bg-blue-600"
        >
          <Switch.Thumb className="block w-5 h-5 bg-white rounded-full transition-transform duration-100 translate-x-0.5 will-change-transform data-[state=checked]:translate-x-[22px]" />
        </Switch.Root>
      </div>

      {/* Notify Subscribers Switch */}
      <div className="flex items-center justify-between">
        <Label.Root htmlFor="notify-subscribers" className="text-sm font-medium">
          Notify Subscribers
        </Label.Root>
        <Switch.Root
          id="notify-subscribers"
          checked={notifySubscribers}
          onCheckedChange={(checked) => setValue('notifySubscribers', checked)}
          className="w-11 h-6 bg-gray-200 rounded-full relative data-[state=checked]:bg-blue-600"
        >
          <Switch.Thumb className="block w-5 h-5 bg-white rounded-full transition-transform duration-100 translate-x-0.5 will-change-transform data-[state=checked]:translate-x-[22px]" />
        </Switch.Root>
      </div>

      {/* Form Actions */}
      <div className="flex justify-end space-x-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting || isUploading || !videoFile}
          className={cn(
            'px-4 py-2 bg-blue-600 text-white rounded-md',
            'hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {isUploading ? 'Uploading...' : 'Upload Video'}
        </button>
      </div>
    </form>
  )
}