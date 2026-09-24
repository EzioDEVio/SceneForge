import React, {useState} from 'react';
import {Film} from 'lucide-react';
import {api} from './api';

/** Cached server thumbnail for an image or a poster frame for a video.
 *  Falls back to the film icon if the file cannot be decoded. */
export function Thumb({assetId, type, width = 320, iconSize = 22}: {assetId: string; type?: string; width?: number; iconSize?: number}) {
  const [failed, setFailed] = useState(false);
  if (failed || !type || type === 'audio') return <Film size={iconSize}/>;
  return <>
    <img src={api.assetThumbUrl(assetId, width)} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)}/>
    {type === 'video' && <span className="thumb-video-badge" aria-label="Video"><Film size={11}/></span>}
  </>;
}
