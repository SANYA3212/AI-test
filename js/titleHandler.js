// js/titleHandler.js

export async function fetchGeneratedTitle(chatHistory, modelNameForTitle) {
    console.log('[TitleHandler] Requesting title generation. Model:', modelNameForTitle, 'History length:', chatHistory.length);
    try {
        const titleResponse = await fetch('/generate-title', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                history: chatHistory,
                model: modelNameForTitle 
            })
        });

        if (titleResponse.ok) {
            const titleData = await titleResponse.json();
            if (titleData.title) {
                console.log('[TitleHandler] Received title:', titleData.title);
                return titleData.title;
            } else {
                console.error('[TitleHandler] Title generation successful but no title in response:', titleData);
                return null;
            }
        } else {
            const errorData = await titleResponse.text();
            console.error('[TitleHandler] Title generation request failed:', titleResponse.status, errorData);
            return null;
        }
    } catch (error) {
        console.error('[TitleHandler] Error during title generation request:', error);
        return null;
    }
}
