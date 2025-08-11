import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { composioApi, type ComposioProfile, type ComposioToolkitGroup, type ComposioMcpUrlResponse } from './utils';
import { composioKeys } from './keys';
import { toast } from 'sonner';

export const useComposioProfiles = (params?: { toolkit_slug?: string; is_active?: boolean }) => {
  return useQuery({
    queryKey: composioKeys.profiles.list(params),
    queryFn: () => composioApi.getProfiles(params),
    staleTime: 5 * 60 * 1000,
  });
};

// Hook to get a single profile
export const useComposioProfile = (profileId: string, enabled = true) => {
  return useQuery({
    queryKey: composioKeys.profiles.detail(profileId),
    queryFn: async () => {
      const profiles = await composioApi.getProfiles();
      return profiles.find(p => p.profile_id === profileId) || null;
    },
    enabled: enabled && !!profileId,
    staleTime: 5 * 60 * 1000,
  });
};

export const useComposioCredentialsProfiles = () => {
  return useQuery({
    queryKey: composioKeys.profiles.all(),
    queryFn: () => composioApi.getCredentialsProfiles(),
    staleTime: 5 * 60 * 1000,
  });
};

export const useComposioMcpUrl = (profileId: string, enabled = false) => {
  return useQuery({
    queryKey: composioKeys.profiles.mcpConfig(profileId),
    queryFn: () => composioApi.getMcpUrl(profileId),
    enabled: enabled && !!profileId,
    staleTime: 0,
    gcTime: 0,
  });
};

export const useDeleteComposioProfile = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (profileId: string) => composioApi.deleteProfile(profileId),
    onSuccess: () => {
      // Invalidate all profile-related queries
      queryClient.invalidateQueries({ queryKey: composioKeys.profiles.all() });
      toast.success('Profile deleted successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to delete profile');
    },
  });
}; 