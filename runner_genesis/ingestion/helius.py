from __future__ import annotations
from datetime import datetime, timezone
import hashlib
from ..domain.events import MarketEvent, EventType

class HeliusWebhookNormalizer:
    """Conservative normalizer for already-decoded webhook/enhanced transaction payloads.

    It does not infer a token by symbol. token_mint must be explicit in a transfer or supplied
    by an upstream parser that has verified the mint.
    """
    def normalize(self,payload:dict)->list[MarketEvent]:
        out=[]
        sig=payload.get('signature') or payload.get('transactionSignature')
        ts=payload.get('timestamp') or payload.get('blockTime')
        if isinstance(ts,(int,float)): ts=datetime.fromtimestamp(ts,tz=timezone.utc)
        elif isinstance(ts,str): ts=datetime.fromisoformat(ts.replace('Z','+00:00'))
        else: ts=datetime.now(timezone.utc)
        slot=payload.get('slot')
        transfers=payload.get('tokenTransfers') or []
        native=payload.get('nativeTransfers') or []
        for i,tr in enumerate(transfers):
            mint=tr.get('mint') or tr.get('tokenMint')
            if not mint: continue
            frm=tr.get('fromUserAccount') or tr.get('fromTokenAccount')
            to=tr.get('toUserAccount') or tr.get('toTokenAccount')
            amount=tr.get('tokenAmount') or tr.get('amount')
            eid=hashlib.sha256(f'{sig}|token|{i}|{mint}'.encode()).hexdigest()[:24]
            out.append(MarketEvent(event_id=eid,timestamp=ts,slot=slot,tx_signature=sig,token_mint=mint,wallet=to,counterparty=frm,event_type=EventType.TRANSFER,amount_token=float(amount or 0),source='helius_webhook',asset_match_verified=True,metadata={'raw_type':payload.get('type')}))
        return out

class HeliusParsedEventNormalizer:
    """Normalizer for Helius Parsed Events / Parsed Streams summary payloads.

    Supports explicit swap summaries with input_mint/output_mint. Amounts may be raw units;
    token decimals must be resolved separately before executable sizing.
    """
    WSOL='So11111111111111111111111111111111111111112'
    def normalize(self,payload:dict)->list[MarketEvent]:
        summary=payload.get('summary') or {}
        parsed=summary.get('parsedData') or summary.get('parsed_data') or {}
        if str(summary.get('type','')).lower()!='swap': return []
        in_mint=parsed.get('input_mint'); out_mint=parsed.get('output_mint')
        if not in_mint or not out_mint: return []
        wallet=None
        for ins in payload.get('instructions') or []:
            for acc in ins.get('decoded',{}).get('accounts',[]) or []:
                if acc.get('name') in ('user_transfer_authority','user','owner'):
                    wallet=acc.get('pubkey'); break
            if wallet: break
        ts=payload.get('timestamp') or payload.get('blockTime')
        if isinstance(ts,(int,float)): ts=datetime.fromtimestamp(ts,tz=timezone.utc)
        elif isinstance(ts,str): ts=datetime.fromisoformat(ts.replace('Z','+00:00'))
        else: ts=datetime.now(timezone.utc)
        sig=payload.get('signature') or payload.get('transactionSignature') or hashlib.sha256(repr(payload).encode()).hexdigest()
        if in_mint==self.WSOL and out_mint!=self.WSOL:
            mint=out_mint; et=EventType.BUY; sol_raw=float(parsed.get('in_amount') or 0); sol=sol_raw/1e9
            amt=float(parsed.get('actual_out_amount') or parsed.get('out_amount') or 0)
        elif out_mint==self.WSOL and in_mint!=self.WSOL:
            mint=in_mint; et=EventType.SELL; sol_raw=float(parsed.get('actual_out_amount') or parsed.get('out_amount') or 0); sol=sol_raw/1e9
            amt=float(parsed.get('in_amount') or 0)
        else:
            return []
        return [MarketEvent(event_id=hashlib.sha256(f'{sig}|swap|{mint}'.encode()).hexdigest()[:24],timestamp=ts,slot=payload.get('slot'),tx_signature=sig,token_mint=mint,wallet=wallet,event_type=et,amount_token=amt,sol_value=sol,source='helius_parsed_events',asset_match_verified=True,metadata={'protocol':parsed.get('protocol'),'amount_units':'raw_token_units_unless_decimals_resolved'})]


class HeliusOnChainNormalizer(HeliusParsedEventNormalizer):
    USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
    QUOTES={HeliusParsedEventNormalizer.WSOL,USDC}

    def normalize(self,payload:dict)->list[MarketEvent]:
        out=[]
        # Explicit decoded token creation/initialization events.
        ts=payload.get('timestamp') or payload.get('blockTime')
        if isinstance(ts,(int,float)): ts=datetime.fromtimestamp(ts,tz=timezone.utc)
        elif isinstance(ts,str): ts=datetime.fromisoformat(ts.replace('Z','+00:00'))
        else: ts=datetime.now(timezone.utc)
        sig=payload.get('signature') or payload.get('transactionSignature') or hashlib.sha256(repr(payload).encode()).hexdigest()
        for j,ins in enumerate(payload.get('instructions') or []):
            dec=ins.get('decoded') or {}; name=str(ins.get('instructionName') or dec.get('name') or '').lower()
            if not any(k in name for k in ('create','initialize')): continue
            mint=None; creator=None
            for a in dec.get('accounts',[]) or []:
                an=str(a.get('name','')).lower(); pub=a.get('pubkey')
                if an in ('mint','base_mint','token_mint') and pub: mint=pub
                if an in ('user','creator','payer','authority') and pub and creator is None: creator=pub
            if mint:
                out.append(MarketEvent(event_id=hashlib.sha256(f'{sig}|create|{j}|{mint}'.encode()).hexdigest()[:24],timestamp=ts,slot=payload.get('slot'),tx_signature=sig,token_mint=mint,wallet=creator,event_type=EventType.TOKEN_CREATED,source='helius_parsed_events',asset_match_verified=True,metadata={'instruction_name':name,'program':ins.get('programName')}))
        summary=payload.get('summary') or {}; parsed=summary.get('parsedData') or summary.get('parsed_data') or {}
        if str(summary.get('type','')).lower()!='swap': return out
        in_mint=parsed.get('input_mint'); out_mint=parsed.get('output_mint')
        if not in_mint or not out_mint: return out
        wallet=None
        for ins in payload.get('instructions') or []:
            for acc in (ins.get('decoded') or {}).get('accounts',[]) or []:
                if acc.get('name') in ('user_transfer_authority','user','owner','payer'):
                    wallet=acc.get('pubkey'); break
            if wallet: break
        in_raw=float(parsed.get('in_amount') or 0); out_raw=float(parsed.get('actual_out_amount') or parsed.get('out_amount') or 0)
        if in_mint in self.QUOTES and out_mint not in self.QUOTES:
            mint=out_mint; et=EventType.BUY; amount=out_raw
            sol=in_raw/1e9 if in_mint==self.WSOL else None
            usd=in_raw/1e6 if in_mint==self.USDC else None
        elif out_mint in self.QUOTES and in_mint not in self.QUOTES:
            mint=in_mint; et=EventType.SELL; amount=in_raw
            sol=out_raw/1e9 if out_mint==self.WSOL else None
            usd=out_raw/1e6 if out_mint==self.USDC else None
        else: return out
        out.append(MarketEvent(event_id=hashlib.sha256(f'{sig}|swap|{mint}'.encode()).hexdigest()[:24],timestamp=ts,slot=payload.get('slot'),tx_signature=sig,token_mint=mint,wallet=wallet,event_type=et,amount_token=amount,sol_value=sol,usd_value=usd,source='helius_parsed_events',asset_match_verified=True,metadata={'protocol':parsed.get('protocol'),'input_mint':in_mint,'output_mint':out_mint,'token_amount_units':'raw_until_decimals_resolved'}))
        return out
