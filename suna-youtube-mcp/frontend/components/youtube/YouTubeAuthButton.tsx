/**
 * YouTube Authentication Button Component
 * Handles OAuth popup flow and authentication
 * Uses Radix UI components following Suna's tech stack
 */

import React, { useState, useEffect } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import * as Button from '@radix-ui/react-button'
import { ExternalLink, Youtube, Loader2 } from 'lucide-react'
import { useYouTubeStore } from '@/stores/youtube-store'
import { cn } from '@/lib/utils'

interface YouTubeAuthButtonProps {
  authUrl?: string
  onSuccess?: (channel: any) => void
  onError?: (error: string) => void
  className?: string
}

export function YouTubeAuthButton({
  authUrl,
  onSuccess,
  onError,
  className
}: YouTubeAuthButtonProps) {
  const [isAuthenticating, setIsAuthenticating] = useState(false)
  const { setChannel, setAuthenticating } = useYouTubeStore()

  useEffect(() => {
    // Listen for OAuth success/error messages
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'youtube-auth-success') {
        setIsAuthenticating(false)
        setAuthenticating(false)
        
        const account = event.data.account
        
        // Update store
        setChannel({
          id: account.id,
          name: account.name,
          thumbnail_url: account.thumbnail,
          custom_url: account.username
        })
        
        // Callback
        onSuccess?.(account)
        
        console.log('[YouTubeAuth] Authentication successful:', account)
      } else if (event.data?.type === 'youtube-auth-error') {
        setIsAuthenticating(false)
        setAuthenticating(false)
        
        const error = event.data.error || 'Authentication failed'
        console.error('[YouTubeAuth] Authentication error:', error)
        
        onError?.(error)
      }
    }

    window.addEventListener('message', handleMessage)
    
    return () => {
      window.removeEventListener('message', handleMessage)
    }
  }, [onSuccess, onError, setChannel, setAuthenticating])

  const handleAuth = () => {
    if (!authUrl) {
      console.error('[YouTubeAuth] No auth URL provided')
      onError?.('No authentication URL available')
      return
    }

    console.log('[YouTubeAuth] Opening auth popup')
    setIsAuthenticating(true)
    setAuthenticating(true)

    // Open OAuth popup
    const width = 600
    const height = 700
    const left = window.screen.width / 2 - width / 2
    const top = window.screen.height / 2 - height / 2
    
    const authWindow = window.open(
      authUrl,
      'youtube-auth',
      `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`
    )

    // Monitor if window closes without completing
    if (authWindow) {
      const checkClosed = setInterval(() => {
        if (authWindow.closed) {
          clearInterval(checkClosed)
          
          // Give a moment for success message to arrive
          setTimeout(() => {
            if (isAuthenticating) {
              console.log('[YouTubeAuth] Auth window closed without completion')
              setIsAuthenticating(false)
              setAuthenticating(false)
              
              // Check if account was actually connected
              checkAccountStatus()
            }
          }, 1000)
        }
      }, 1000)
    }
  }

  const checkAccountStatus = async () => {
    try {
      const response = await fetch('/api/youtube/channels')
      const data = await response.json()
      
      if (data.channels && data.channels.length > 0) {
        const channel = data.channels[0]
        console.log('[YouTubeAuth] Channel found after auth:', channel)
        
        setChannel(channel)
        onSuccess?.(channel)
      } else {
        console.log('[YouTubeAuth] No channels found after auth')
      }
    } catch (error) {
      console.error('[YouTubeAuth] Error checking account status:', error)
    }
  }

  return (
    <button
      onClick={handleAuth}
      disabled={isAuthenticating || !authUrl}
      className={cn(
        'inline-flex items-center justify-center rounded-md px-4 py-2',
        'bg-red-600 text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'transition-colors duration-200',
        className
      )}
    >
      {isAuthenticating ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Authenticating...
        </>
      ) : (
        <>
          <Youtube className="mr-2 h-4 w-4" />
          Authenticate with YouTube
        </>
      )}
    </button>
  )
}

/**
 * YouTube Account Card Component
 * Displays connected YouTube account information
 */
export function YouTubeAccountCard() {
  const { channel, clearChannel } = useYouTubeStore()

  if (!channel) {
    return null
  }

  return (
    <div className="flex items-center justify-between p-4 border rounded-lg bg-white dark:bg-gray-800">
      <div className="flex items-center gap-3">
        {channel.thumbnail_url && (
          <img
            src={channel.thumbnail_url}
            alt={channel.name}
            className="w-10 h-10 rounded-full"
          />
        )}
        <div>
          <p className="font-medium">{channel.name}</p>
          {channel.custom_url && (
            <p className="text-sm text-gray-500">@{channel.custom_url}</p>
          )}
        </div>
      </div>
      
      <button
        onClick={clearChannel}
        className="px-3 py-1 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors"
      >
        Disconnect
      </button>
    </div>
  )
}