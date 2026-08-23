<LTMPage Version="15" Description="Cardiac Arrest PedQuEST Trends">
<ArtifactReduction UseImpedance="1" ImpedanceThresholdKOhm="50" UseDisconnectDetector="0" MissingAsOpen="1" CalculateAR="1" ExcludedChannelList=""/>
<Channels Name="BP-Longitudinal" LowFilter="1 Hz" HighFilter="35 Hz" NotchFilter="(On)" CustomFilter="(off)"/>
<Instruments>
<Montage ClassName="Montage">
<Engine ByEpochFlags="0" EpochDuration="3" EpochStep="2" EpochStepUseDefault="0" EpochDataIsCentered="1" EpochAnchor="0" EpochAnchorIsVariable="0" EngineName="RhythmicityEngine01" WaveformRate="128" ResampleMethod="2" EngineFlags="72" P2D2FreqMin="1" P2D2FreqMax="25" Iterations="4" ClsId="{B60E5A23-16AE-476D-858E-B9C02BF20E3F}" RefId="85234688"/>
<Engine ByEpochFlags="0" EpochDuration="1" EpochStep="1" EpochStepUseDefault="1" EpochDataIsCentered="0" EpochAnchor="0" EpochAnchorIsVariable="0" EngineName="PeakEnvelope01" WaveformRate="128" ResampleMethod="2" EngineFlags="72" FreqMax="20" FreqMin="2" ClsId="{75898259-39B8-45CA-9151-3958F7DB2527}" RefId="181556088"/>
<Engine ByEpochFlags="0" EpochDuration="10" EpochStep="10" EpochStepUseDefault="1" EpochDataIsCentered="0" EpochAnchor="0" EpochAnchorIsVariable="0" EngineName="Amplitude01" WaveformRate="128" ResampleMethod="2" EngineFlags="72" FlatAmpThreshold="3" FlatDurThreshold="0.5" ClsId="{764B0852-DF6D-4A15-8AE0-7D3105D1C27A}" RefId="181913688"/>
<Engine ByEpochFlags="0" EpochDuration="1" EpochStep="1" EpochStepUseDefault="1" EpochDataIsCentered="0" EpochAnchor="0" EpochAnchorIsVariable="0" EngineName="aEEG01" WaveformRate="64" ResampleMethod="2" EngineFlags="72" HighFilter="26 Hz" LowFilter="0.8 Hz" NotchFilter="50+60 Hz" CustomFilter="" ClsId="{BE6A543C-E969-4159-9A5F-903189E6EE1C}" RefId="181915752"/>
<Engine ByEpochFlags="1" EpochDuration="4" EpochStep="8" EpochStepUseDefault="0" EpochDataIsCentered="0" EpochAnchor="0" EpochAnchorIsVariable="0" EngineName="FFTEngine01" WaveformRate="64" ResampleMethod="2" EngineFlags="73" PtsPerWindow="128" SmoothFactor="3" WindowType="7" WindowsPerEpoch="4" OverlapWindows="1" ClsId="{A0A5E108-3D72-11D6-809D-006008184043}" RefId="181921584"/>
<Engine ByEpochFlags="16" EpochDuration="1.2" EpochStep="1" EpochStepUseDefault="0" EpochDataIsCentered="1" EpochAnchor="0" EpochAnchorIsVariable="0" EngineName="Artifact01" WaveformRate="128" ResampleMethod="2" EngineFlags="0" ArtifactChannelsType="0" ClsId="{9DFC3C2E-A385-4BB2-A8E0-1FAF5D4F9CFC}" RefId="181924032"/>
<Engine EpochDuration="1" EpochStep="1" EpochStepUseDefault="1" EngineName="Heart Rate Engine01" EngineFlags="64" ClsId="{42B25590-3F6D-47AF-97EC-B64BD0460525}" RefId="181954448"/>
<Engine EpochDuration="1" EpochStep="1" EpochStepUseDefault="1" EngineName="Heart Rate Engine" EngineFlags="64" ClsId="{42B25590-3F6D-47AF-97EC-B64BD0460525}" RefId="181954808"/>
<Engine ByEpochFlags="48" EpochDuration="1" EpochStep="1" EpochStepUseDefault="0" EpochDataIsCentered="0" EpochAnchor="0" EpochAnchorIsVariable="0" EngineName="SpikeDensityV101" WaveformRate="128" ResampleMethod="2" EngineFlags="66" Protocol="&lt;RevealProtocol Name=&quot;DefaultScalp&quot;&gt;
&lt;Detector Name=&quot;Spike&quot;&gt;
&lt;Montage AlwaysUseGrid2=&quot;1&quot; MasterControl=&quot;2&quot; UvPerMM=&quot;10 uV&quot; LowFilter=&quot;1 Hz&quot; HighFilter=&quot;(off)&quot; NotchFilter=&quot;50+60 Hz&quot; UseScalpSign=&quot;0&quot; Use1020Topology=&quot;1&quot; MontageName=&quot;Ref-Group Av12&quot; DetectionFlags=&quot;1&quot;&gt;
&lt;Channel Name=&quot;Fz-Av12&quot; Definition=&quot;Fz-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;Cz-Av12&quot; Definition=&quot;Cz-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;Pz-Av12&quot; Definition=&quot;Pz-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;Fp1-Av12&quot; Definition=&quot;Fp1-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;F3-Av12&quot; Definition=&quot;F3-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;C3-Av12&quot; Definition=&quot;C3-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;P3-Av12&quot; Definition=&quot;P3-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;O1-Av12&quot; Definition=&quot;O1-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;Fp2-Av12&quot; Definition=&quot;Fp2-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;F4-Av12&quot; Definition=&quot;F4-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;C4-Av12&quot; Definition=&quot;C4-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;P4-Av12&quot; Definition=&quot;P4-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;O2-Av12&quot; Definition=&quot;O2-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;F7-Av12&quot; Definition=&quot;F7-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;T3-Av12&quot; Definition=&quot;T3-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;T5-Av12&quot; Definition=&quot;T5-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;F8-Av12&quot; Definition=&quot;F8-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;T4-Av12&quot; Definition=&quot;T4-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;T6-Av12&quot; Definition=&quot;T6-Av12&quot; MasterControl=&quot;1&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;268435457&quot;/&gt;
&lt;Channel Name=&quot;Fp12-Cz&quot; Definition=&quot;Fp12-Cz&quot; MasterControl=&quot;0&quot; UvPerMM=&quot;10 uV&quot; LowFilter=&quot;1 Hz&quot; HighFilter=&quot;15 Hz&quot; NotchFilter=&quot;50+60 Hz&quot; CustomFilter=&quot;(off)&quot; PolyMinimum=&quot;0&quot; PolyMaximum=&quot;100&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;2&quot;/&gt;
&lt;Channel Name=&quot;F7-F8&quot; Definition=&quot;F7-F8&quot; MasterControl=&quot;0&quot; UvPerMM=&quot;10 uV&quot; LowFilter=&quot;1 Hz&quot; HighFilter=&quot;15 Hz&quot; NotchFilter=&quot;50+60 Hz&quot; CustomFilter=&quot;(off)&quot; ResampleMethod=&quot;2&quot; ResampleRate=&quot;200&quot; Process=&quot;1&quot; ChannelCode=&quot;4&quot;/&gt;
&lt;AvgRef Name=&quot;A1A2&quot; Definition=&quot;A1+A2&quot;/&gt;
&lt;AvgRef Name=&quot;Av17&quot; Definition=&quot;F7+F3+Fz+F4+F8+T3+C3+Cz+C4+T4+T5+P3+Pz+P4+T6+O1+O2&quot;/&gt;
&lt;AvgRef Name=&quot;Av12&quot; Definition=&quot;F3+F4+T3+C3+C4+T4+T5+P3+P4+T6+O1+O2&quot;/&gt;
&lt;AvgRef Name=&quot;AvFp12&quot; Definition=&quot;Fp1+Fp2&quot;/&gt;
&lt;AvgRef Name=&quot;AvT34&quot; Definition=&quot;T3+T4&quot;/&gt;
&lt;AvgRef Name=&quot;AvO12&quot; Definition=&quot;O1+O2&quot;/&gt;
&lt;AvgRef Name=&quot;Fp12&quot; Definition=&quot;Fp1+Fp2&quot;/&gt;
&lt;/Montage&gt;
&lt;Settings&gt;
&lt;Event Name=&quot;Spike&quot; Type=&quot;0&quot; Detect=&quot;1&quot; Perception=&quot;0.1&quot; Duration=&quot;0&quot;/&gt;
&lt;Event Name=&quot;Spike&quot; Type=&quot;1&quot; Detect=&quot;0&quot; Perception=&quot;0.4&quot; Duration=&quot;0&quot;/&gt;
&lt;Event Name=&quot;SpikeBurst&quot; Type=&quot;0&quot; Detect=&quot;1&quot; Perception=&quot;0.1&quot; Duration=&quot;1&quot;/&gt;
&lt;Event Name=&quot;SpikeBurst&quot; Type=&quot;1&quot; Detect=&quot;1&quot; Perception=&quot;0.5&quot; Duration=&quot;20&quot;/&gt;
&lt;/Settings&gt;
&lt;/Detector&gt;
&lt;/RevealProtocol&gt;
" ClsId="{7058F50D-5ADC-4A8D-AA62-BD2A50ED9FFB}" RefId="182585092"/>